package org.engram.watch

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Where the Mac is and the token it gave this watch. */
class Pairing(context: Context) {
    private val prefs = context.getSharedPreferences("engram", Context.MODE_PRIVATE)
    var url: String
        get() = prefs.getString("url", "") ?: ""
        set(v) = prefs.edit().putString("url", v.trim().trimEnd('/')).apply()
    var token: String?
        get() = prefs.getString("token", null)
        set(v) = prefs.edit().putString("token", v).apply()
    var watching: Boolean
        get() = prefs.getBoolean("watching", true)
        set(v) = prefs.edit().putBoolean("watching", v).apply()
    val paired get() = url.isNotEmpty() && token != null
    fun api() = Api(url, token)
}

/**
 * Wear OS sends traffic through the phone's Bluetooth proxy by default, which cannot reach the Mac on the LAN. While
 * anyone holds it, this keeps a Wi-Fi network requested; connections open on it (G-watch-agent.md §4). Requesting it
 * wakes the radio, so it is held only while the approval service runs or a request is in flight.
 */
object Net {
    private val _network = MutableStateFlow<Network?>(null)
    val network: StateFlow<Network?> = _network
    private var callback: ConnectivityManager.NetworkCallback? = null
    private var users = 0

    @Synchronized
    fun acquire(context: Context) {
        if (users++ > 0) return
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { _network.value = network }
            override fun onLost(network: Network) { if (_network.value == network) _network.value = null }
        }
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)     // a hotspot LAN is enough
            .build()
        cm.requestNetwork(request, cb)
        callback = cb
    }

    @Synchronized
    fun release(context: Context) {
        if (users == 0 || --users > 0) return
        callback?.let { context.getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) }
        callback = null
        _network.value = null
    }

    /** Hold Wi-Fi around [block]; waits up to 8 s for it to come up, then tries whatever network there is. */
    suspend fun <T> around(context: Context, block: suspend () -> T): T {
        acquire(context)
        try {
            withTimeoutOrNull(8_000) { network.filterNotNull().first() }
            return block()
        } finally {
            release(context)
        }
    }
}

class ApiError(val status: Int, message: String) : Exception(message)

data class Pending(
    val run: String, val request: String, val tool: String, val effect: String, val preview: String,
    val judge: String?, val onWatch: Boolean,
    val headline: String? = null,           // a meeting reply's "Nia: Thursday 11:30 AM, you're free" (meeting.py)
    val reply: String? = null,              // ...and the draft it would send
) {
    val title get() = headline ?: if (onWatch) "Approve? $tool" else "On the laptop: $tool"
    val text get() = reply ?: preview
}

/** Something a role sends the owner (engram/herald.py): buzz-worthy ([now]) or for the digest. */
data class Card(
    val id: Long, val role: String, val kind: String, val title: String, val body: String,
    val actions: List<Pair<String, String>>, val now: Boolean, val why: String,
)

data class Feed(val version: Int, val cards: List<Card>, val approvals: List<Pending>)

data class Reply(val heard: String?, val kind: String, val answer: String?, val cites: List<String>, val seconds: Double?)

/** The Mac's watch endpoints (engram serve --lan). Blocking: call from Dispatchers.IO. */
class Api(private val base: String, private val token: String?) {

    fun hello(): Boolean = call("/watch/hello", timeoutMs = 5_000).optBoolean("engram")

    /** The server's HMAC(token hash, nonce) for each watch paired with it (Discovery.proves). */
    fun proofs(nonce: String): Set<String> {
        val a = call("/watch/hello?nonce=$nonce", timeoutMs = 5_000).optJSONArray("proofs") ?: return emptySet()
        return List(a.length()) { a.getString(it) }.toSet()
    }

    fun pair(code: String, name: String): String =
        call("/watch/pair", json = JSONObject().put("code", code).put("name", name)).getString("token")

    /**
     * Pending approvals and Herald's cards from the other roles, and the version they are at; with [since], waits
     * up to [wait] s for a change first.
     */
    fun pending(since: Int?, wait: Int): Feed {
        val r = call("/watch/pending?wait=$wait" + (since?.let { "&since=$it" } ?: ""), timeoutMs = (wait + 10) * 1000)
        val list = r.getJSONArray("pending")
        val cards = r.optJSONArray("cards")
        return Feed(r.getInt("version"), List(cards?.length() ?: 0) { i ->
            val c = cards!!.getJSONObject(i)
            val a = c.getJSONArray("actions")
            Card(c.getLong("id"), c.getString("role"), c.getString("kind"), c.getString("title"), c.optString("body"),
                 List(a.length()) { a.getJSONObject(it).let { x -> x.getString("id") to x.getString("label") } },
                 c.getString("route") == "now", c.optString("why"))
        }, List(list.length()) { i ->
            val p = list.getJSONObject(i)
            val j = p.optJSONObject("judge")
            Pending(
                p.getString("run"), p.getString("request"), p.getString("tool"), p.getString("effect"),
                p.getString("preview"),
                j?.let { "${if (it.optBoolean("settled")) "sure" else "unsure"}: ${it.optString("value")} " +
                         "(p=${"%.2f".format(it.optDouble("p"))})" },
                p.optBoolean("on_watch"),
                p.optJSONObject("card")?.optString("headline")?.ifEmpty { null },
                p.optJSONObject("card")?.optString("reply")?.ifEmpty { null },
            )
        })
    }

    fun card(id: Long, action: String) {
        call("/watch/card", json = JSONObject().put("id", id).put("action", action))
    }

    fun decide(run: String, approve: Boolean) {
        call("/watch/decide", json = JSONObject().put("run", run).put("approve", approve))
    }

    fun ask(question: String): Reply = reply(call("/watch/ask", json = JSONObject().put("question", question),
                                                  timeoutMs = 90_000))

    fun voice(wav: ByteArray): Reply = reply(call("/watch/voice", body = wav, type = "audio/wav", timeoutMs = 90_000))

    private fun reply(r: JSONObject): Reply {
        val cites = r.optJSONArray("cites")
        return Reply(
            r.optString("heard").ifEmpty { null }, r.optString("kind"), r.optString("answer").ifEmpty { null },
            List(cites?.length() ?: 0) { cites!!.getString(it) },
            if (r.has("seconds")) r.getDouble("seconds") else null,
        )
    }

    private fun call(path: String, json: JSONObject? = null, body: ByteArray? = json?.toString()?.toByteArray(),
                     type: String = "application/json", timeoutMs: Int = 15_000): JSONObject {
        val url = URL(base + path)
        val c = (Net.network.value?.openConnection(url) ?: url.openConnection()) as HttpURLConnection
        try {
            c.connectTimeout = 5_000
            c.readTimeout = timeoutMs
            token?.let { c.setRequestProperty("Authorization", "Bearer $it") }
            if (body != null) {
                c.requestMethod = "POST"
                c.doOutput = true
                c.setRequestProperty("Content-Type", type)
                c.setFixedLengthStreamingMode(body.size)
                c.outputStream.use { it.write(body) }
            }
            val status = c.responseCode
            val text = (if (status < 400) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() }
            val r = runCatching { JSONObject(text ?: "{}") }.getOrElse { JSONObject() }
            if (status >= 400) throw ApiError(status, r.optString("error").ifEmpty { "HTTP $status" })
            return r
        } finally {
            c.disconnect()
        }
    }
}

suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }
