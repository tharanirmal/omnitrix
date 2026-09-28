package org.engram.watch

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.io.IOException
import java.net.Inet4Address
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.Executor
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.coroutines.resume

/**
 * Finding the Mac again when the hotspot gives it a new address: it announces `_engram._tcp` over mDNS
 * (engram/watch.py). Anyone on the network could announce that, so the token goes only to a server that proves it
 * holds the token's hash (an HMAC of a fresh nonce) before it is ever sent.
 */
object Discovery {
    private const val SERVICE = "_engram._tcp"
    private val direct = Executor { it.run() }

    /** The watch listeners announced on the network: "http://ip:port", IPv4 only. */
    suspend fun find(context: Context, listenMs: Long = 4_000): List<String> {
        val nsd = context.getSystemService(NsdManager::class.java)
        val found = mutableListOf<NsdServiceInfo>()
        val listener = object : NsdManager.DiscoveryListener {
            override fun onServiceFound(info: NsdServiceInfo) { synchronized(found) { found += info } }
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onDiscoveryStarted(type: String) {}
            override fun onDiscoveryStopped(type: String) {}
            override fun onStartDiscoveryFailed(type: String, code: Int) {}
            override fun onStopDiscoveryFailed(type: String, code: Int) {}
        }
        val network = Net.network.value
        if (Build.VERSION.SDK_INT >= 33 && network != null) {
            nsd.discoverServices(SERVICE, NsdManager.PROTOCOL_DNS_SD, network, direct, listener)
        } else {
            nsd.discoverServices(SERVICE, NsdManager.PROTOCOL_DNS_SD, listener)
        }
        try {
            delay(listenMs)
        } finally {
            runCatching { nsd.stopServiceDiscovery(listener) }
        }
        return synchronized(found) { found.toList() }.flatMap { resolve(nsd, it) }.distinct()
    }

    /** Moves [pairing] to wherever its Mac is now; false if no announced server proves it is that Mac. */
    suspend fun relocate(context: Context, pairing: Pairing): Boolean {
        val token = pairing.token ?: return false
        for (url in find(context)) {
            if (url != pairing.url && runCatching { io { proves(Api(url, null), token) } }.getOrDefault(false)) {
                pairing.url = url
                return true
            }
        }
        return false
    }

    fun proves(api: Api, token: String): Boolean {
        val nonce = ByteArray(16).also(SecureRandom()::nextBytes).hex()
        val key = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).hex().toByteArray()
        val mac = Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(key, "HmacSHA256")) }
        return mac.doFinal(nonce.toByteArray()).hex() in api.proofs(nonce)
    }

    private suspend fun resolve(nsd: NsdManager, info: NsdServiceInfo): List<String> {
        if (Build.VERSION.SDK_INT >= 34) {
            var callback: NsdManager.ServiceInfoCallback? = null
            try {
                return withTimeoutOrNull(3_000) {
                    suspendCancellableCoroutine { cont ->
                        callback = object : NsdManager.ServiceInfoCallback {
                            override fun onServiceUpdated(s: NsdServiceInfo) {
                                if (cont.isActive) cont.resume(s.hostAddresses.filterIsInstance<Inet4Address>()
                                    .map { "http://${it.hostAddress}:${s.port}" })
                            }
                            override fun onServiceInfoCallbackRegistrationFailed(code: Int) {
                                if (cont.isActive) cont.resume(emptyList())
                            }
                            override fun onServiceLost() {}
                            override fun onServiceInfoCallbackUnregistered() {}
                        }.also { nsd.registerServiceInfoCallback(info, direct, it) }
                    }
                } ?: emptyList()
            } finally {
                callback?.let { runCatching { nsd.unregisterServiceInfoCallback(it) } }
            }
        }
        return withTimeoutOrNull(3_000) {
            suspendCancellableCoroutine { cont ->
                @Suppress("DEPRECATION")
                nsd.resolveService(info, object : NsdManager.ResolveListener {
                    override fun onServiceResolved(s: NsdServiceInfo) {
                        @Suppress("DEPRECATION") val host = s.host
                        if (cont.isActive) cont.resume(
                            if (host is Inet4Address) listOf("http://${host.hostAddress}:${s.port}") else emptyList())
                    }
                    override fun onResolveFailed(s: NsdServiceInfo, code: Int) {
                        if (cont.isActive) cont.resume(emptyList())
                    }
                })
            }
        } ?: emptyList()
    }

    private fun ByteArray.hex() = joinToString("") { "%02x".format(it) }
}

/**
 * One request to the paired Mac, over Wi-Fi. If it cannot be reached and no longer answers at its address, find
 * where it went (mDNS, proven) and try once more there.
 */
suspend fun <T> Pairing.request(context: Context, block: (Api) -> T): T = Net.around(context) {
    try {
        io { block(api()) }
    } catch (e: IOException) {
        val stillThere = runCatching { io { Api(url, null).hello() } }.getOrDefault(false)
        if (stillThere || !Discovery.relocate(context, this)) throw e
        io { block(api()) }
    }
}
