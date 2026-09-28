package org.engram.watch

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.wear.ongoing.OngoingActivity
import androidx.wear.ongoing.Status
import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** What the service knows, for the screen to show. */
object Approvals {
    val pending = MutableStateFlow<List<Pending>>(emptyList())
    val cards = MutableStateFlow<List<Card>>(emptyList())
    val status = MutableStateFlow("off")
}

/**
 * Watches for actions the gate escalates, fully locally: a long-poll to the Mac (no cloud push), held by a
 * foreground service shown as an Ongoing Activity (G-watch-agent.md §5). A new approval buzzes with Approve / Deny;
 * destructive actions are shown but decided on the laptop.
 */
class ApprovalService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var pairing: Pairing
    private val shown = mutableSetOf<String>()
    private var loop: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        pairing = Pairing(this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(ONGOING, "Watching", NotificationManager.IMPORTANCE_LOW))
        nm.createNotificationChannel(NotificationChannel(APPROVALS, "Approvals", NotificationManager.IMPORTANCE_HIGH)
            .apply { vibrationPattern = longArrayOf(0, 120, 80, 120); enableVibration(true) })
        val builder = NotificationCompat.Builder(this, ONGOING)
            .setSmallIcon(R.drawable.ic_engram)
            .setContentTitle("engram")
            .setContentText("Watching for approvals")
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setOngoing(true)
        OngoingActivity.Builder(applicationContext, ONGOING_ID, builder)
            .setStaticIcon(R.drawable.ic_engram)
            .setTouchIntent(openApp(this))
            .setStatus(Status.Builder().addTemplate("engram").build())
            .build()
            .apply(applicationContext)
        startForeground(ONGOING_ID, builder.build(), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        Net.acquire(this)
        ensureWatching()
    }

    /** (Re)starts the long-poll loop if it is not running: the app calls start() whenever it opens. */
    private fun ensureWatching() {
        if (loop?.isActive != true) loop = scope.launch { watch() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureWatching()
        if (intent?.action == ACTION_CARD) {
            val id = intent.getLongExtra("card", -1)
            val action = intent.getStringExtra("action") ?: return START_STICKY
            scope.launch {
                runCatching { pairing.api().card(id, action) }
                    .onFailure { Approvals.status.value = "card failed: ${it.message}" }
                getSystemService(NotificationManager::class.java).cancel("card:$id".hashCode())
            }
        }
        if (intent?.action == ACTION_DECIDE) {
            val run = intent.getStringExtra("run") ?: return START_STICKY
            val approve = intent.getBooleanExtra("approve", false)
            scope.launch {
                runCatching { pairing.api().decide(run, approve) }
                    .onFailure { Approvals.status.value = "decide failed: ${it.message}" }
                getSystemService(NotificationManager::class.java).cancel(run.hashCode())
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        scope.cancel()
        Net.release(this)
        Approvals.status.value = "off"
        Approvals.pending.value = emptyList()
        super.onDestroy()
    }

    private suspend fun watch() {
        var since: Int? = null
        var backoff = 2_000L
        var searched = 0L
        while (scope.isActive) {
            try {
                val feed = pairing.api().pending(since, WAIT)
                since = feed.version
                Approvals.pending.value = feed.approvals
                Approvals.cards.value = feed.cards
                status("connected")
                notify(feed)
                backoff = 2_000L
            } catch (e: ApiError) {
                status(if (e.status == 401) "not paired" else "error: ${e.message}")
                if (e.status == 401) { stopSelf(); return }
                retryAfter(backoff)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                status("offline: ${e.javaClass.simpleName}" + (if (Net.network.value == null) ", no Wi-Fi" else ""))
                since = null
                if (System.currentTimeMillis() - searched > 15_000) {     // the hotspot may have moved the Mac
                    searched = System.currentTimeMillis()
                    // guarded: a failure here (mDNS while Wi-Fi flaps) must never end the loop
                    if (runCatching { Discovery.relocate(this, pairing) }.getOrDefault(false)) {
                        status("found the Mac again")
                        backoff = 2_000L
                        continue
                    }
                }
                retryAfter(backoff)
                backoff = minOf(backoff * 2, 30_000L)
            }
        }
    }

    /** Waits [ms], or less: a Wi-Fi network (re)appearing is worth trying at once. */
    private suspend fun retryAfter(ms: Long) {
        withTimeoutOrNull(ms) { Net.network.drop(1).first { it != null } }
    }

    private fun status(s: String) {
        if (Approvals.status.value != s) Log.i("engram", "approvals: $s")
        Approvals.status.value = s
    }

    /** Buzzes once for each new approval and each new buzz-worthy card; clears what is gone. */
    private fun notify(feed: Feed) {
        val nm = getSystemService(NotificationManager::class.java)
        val now = feed.approvals.map { it.run }.toSet() + feed.cards.filter { it.now }.map { "card:${it.id}" }
        (shown - now).forEach { nm.cancel(it.hashCode()) }
        shown.retainAll(now)
        for (c in feed.cards.filter { it.now && "card:${it.id}" !in shown }) {
            val n = NotificationCompat.Builder(this, APPROVALS)
                .setSmallIcon(R.drawable.ic_engram)
                .setContentTitle(c.title)
                .setContentText(c.body)
                .setStyle(NotificationCompat.BigTextStyle().bigText("${c.body}\n\n${c.role} · ${c.why}"))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setContentIntent(openApp(this))
            c.actions.forEach { (id, label) -> n.addAction(0, label, answer(c.id, id)) }
            nm.notify("card:${c.id}".hashCode(), n.build())
            shown += "card:${c.id}"
        }
        for (p in feed.approvals.filter { it.run !in shown }) {
            val n = NotificationCompat.Builder(this, APPROVALS)
                .setSmallIcon(R.drawable.ic_engram)
                .setContentTitle(p.title)
                .setContentText(p.text)
                .setStyle(NotificationCompat.BigTextStyle().bigText(
                    "${p.text}\n\nYou asked: ${p.request}" + (p.judge?.let { "\nJudge: $it" } ?: "")))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setContentIntent(openApp(this))
                .setAutoCancel(false)
            if (p.onWatch) {
                n.addAction(R.drawable.ic_check, "Approve", decide(p.run, true))
                n.addAction(R.drawable.ic_close, "Deny", decide(p.run, false))
            }
            nm.notify(p.run.hashCode(), n.build())
            shown += p.run
        }
    }

    private fun answer(card: Long, action: String): PendingIntent = PendingIntent.getService(
        this, "card:$card:$action".hashCode(),
        Intent(this, ApprovalService::class.java).setAction(ACTION_CARD).putExtra("card", card)
            .putExtra("action", action),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun decide(run: String, approve: Boolean): PendingIntent = PendingIntent.getService(
        this, (run + approve).hashCode(),
        Intent(this, ApprovalService::class.java).setAction(ACTION_DECIDE).putExtra("run", run)
            .putExtra("approve", approve),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    companion object {
        const val ONGOING = "ongoing"
        const val APPROVALS = "approvals"
        const val ONGOING_ID = 1
        const val WAIT = 25                     // seconds per long-poll (the server caps it there too)
        const val ACTION_DECIDE = "org.engram.watch.DECIDE"
        const val ACTION_CARD = "org.engram.watch.CARD"

        fun start(context: Context) = context.startForegroundService(Intent(context, ApprovalService::class.java))
        fun stop(context: Context) = context.stopService(Intent(context, ApprovalService::class.java))

        fun openApp(context: Context): PendingIntent = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
    }
}
