package org.engram.watch

import android.Manifest
import android.app.RemoteInput
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.inputmethod.EditorInfo
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.rememberScalingLazyListState
import androidx.wear.compose.material3.AppScaffold
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.Card
import androidx.wear.compose.material3.FilledTonalButton
import androidx.wear.compose.material3.Icon
import androidx.wear.compose.material3.ListHeader
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.OutlinedButton
import androidx.wear.compose.material3.ScreenScaffold
import androidx.wear.compose.material3.Text
import androidx.wear.compose.material3.TitleCard
import androidx.wear.input.RemoteInputIntentHelper
import androidx.wear.input.wearableExtender
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private val setup = mutableStateOf<Pair<String, String>?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val missing = listOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.POST_NOTIFICATIONS)
            .filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) {
            registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}
                .launch(missing.toTypedArray())
        }
        setup(intent)
        val pairing = Pairing(this)
        setContent { MaterialTheme { AppScaffold { App(pairing, setup) } } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setup(intent)
    }

    /** Pairing from a laptop over adb: `am start -n org.engram.watch/.MainActivity --es url … --es code …`. */
    private fun setup(intent: Intent) {
        val url = intent.getStringExtra("url") ?: return
        setup.value = url to (intent.getStringExtra("code") ?: "")
    }
}

@Composable
private fun App(pairing: Pairing, setup: androidx.compose.runtime.MutableState<Pair<String, String>?>) {
    var paired by remember { mutableStateOf(pairing.paired) }
    if (!paired) {
        PairScreen(pairing, setup) { paired = true }
    } else {
        HomeScreen(pairing) { paired = false }
    }
}

@Composable
private fun PairScreen(pairing: Pairing, setup: androidx.compose.runtime.MutableState<Pair<String, String>?>,
                       onPaired: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf(pairing.url.ifEmpty { "http://" }) }
    var code by remember { mutableStateOf("") }
    var status by remember { mutableStateOf("Run `engram watch pair` on the Mac for a code.") }

    LaunchedEffect(Unit) {                  // the Mac announces itself: no address to type on a watch
        if (url == "http://") {
            status = "Looking for engram on this network…"
            val found = runCatching { Net.around(context) { Discovery.find(context) } }.getOrDefault(emptyList())
            found.firstOrNull()?.let { url = it }
            status = if (found.isEmpty()) "No engram found: enter the Mac's address." else "Found engram. Enter the code."
        }
    }

    fun pair() = scope.launch {
        status = "Pairing…"
        try {
            val token = Net.around(context) {
                io {
                    val api = Api(url.trim().trimEnd('/'), null)
                    check(api.hello()) { "no engram at $url" }
                    api.pair(code.trim(), Build.MODEL)
                }
            }
            pairing.url = url
            pairing.token = token
            onPaired()
        } catch (e: Exception) {
            status = if (e is ApiError && e.status == 403) "Wrong or expired code." else "Failed: ${e.message}"
        }
    }

    LaunchedEffect(setup.value) {
        setup.value?.let { (u, c) ->
            url = u
            code = c
            setup.value = null
            if (c.isNotEmpty()) pair()
        }
    }
    val editUrl = textInput("Mac address") { url = it }
    val editCode = textInput("Pairing code") { code = it.filter(Char::isDigit) }
    Screen {
        item { ListHeader { Text("Pair with engram") } }
        item { FilledTonalButton(onClick = editUrl, label = { Text("Mac") }, secondaryLabel = { Text(url) },
                                 modifier = Modifier.fillMaxWidth()) }
        item { FilledTonalButton(onClick = editCode, label = { Text("Code") },
                                 secondaryLabel = { Text(code.ifEmpty { "tap to enter" }) },
                                 modifier = Modifier.fillMaxWidth()) }
        item { Button(onClick = { pair() }, enabled = code.length == 6, label = { Text("Pair") },
                      modifier = Modifier.fillMaxWidth()) }
        item { Text(status, style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center) }
    }
}

@Composable
private fun HomeScreen(pairing: Pairing, onUnpaired: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val pending by Approvals.pending.collectAsState()
    val cards by Approvals.cards.collectAsState()
    var openCard by remember { mutableStateOf<Card?>(null) }
    var showDigest by remember { mutableStateOf(false) }
    val status by Approvals.status.collectAsState()
    var watching by remember { mutableStateOf(pairing.watching) }
    var selected by remember { mutableStateOf<Pending?>(null) }
    val recorder = remember { Recorder() }
    var listening by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var reply by remember { mutableStateOf<Reply?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(watching) {
        if (watching) ApprovalService.start(context) else ApprovalService.stop(context)
    }

    fun send(call: (Api) -> Reply) = scope.launch {
        busy = true
        error = null
        reply = null
        try {
            reply = pairing.request(context) { call(it) }
        } catch (e: Exception) {
            error = e.message
        } finally {
            busy = false
        }
    }

    fun stopListening() {
        if (!listening) return
        listening = false
        val wav = recorder.stop()
        send { it.voice(wav) }
    }

    LaunchedEffect(listening) {
        if (listening) {
            delay(Recorder.MAX_SECONDS * 1_000L + 300)
            stopListening()
        }
    }
    val typeQuestion = textInput("Ask engram") { q -> send { it.ask(q) } }

    selected?.let { p ->
        ApproveScreen(p, pairing) { selected = null }
        return
    }
    openCard?.let { c ->
        CardScreen(c, pairing) { openCard = null }
        return
    }
    val digest = cards.filterNot { it.now }
    Screen {
        item { ListHeader { Text("engram") } }
        item {
            Text(if (watching) "approvals: $status" else "approvals: off", style = MaterialTheme.typography.bodySmall)
        }
        for (p in pending) {
            item {
                TitleCard(onClick = { selected = p }, title = { Text(p.title) }, modifier = Modifier.fillMaxWidth()) {
                    Text(p.text, maxLines = 3)
                }
            }
        }
        for (c in cards.filter { it.now }) {
            item { CardTile(c) { openCard = c } }
        }
        item {
            Button(
                onClick = {
                    if (listening) stopListening()
                    else if (!busy && ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
                        == PackageManager.PERMISSION_GRANTED) {
                        reply = null
                        error = null
                        recorder.start()
                        listening = true
                    } else if (!busy) error = "Allow the microphone in Settings › Apps › engram."
                },
                icon = { Icon(painterResource(R.drawable.ic_mic), contentDescription = null) },
                label = { Text(when { listening -> "Listening… tap to send"; busy -> "Thinking…"; else -> "Ask or remember" }) },
                secondaryLabel = { if (!listening && !busy) Text("say “remember …” to note") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        reply?.let { r ->
            item {
                Card(onClick = {}, modifier = Modifier.fillMaxWidth()) {
                    r.heard?.let { Text("“$it”", style = MaterialTheme.typography.bodySmall) }
                    Text(if (r.kind == "add") "Saved to memory." else r.answer ?: "(no answer)")
                    r.cites.forEach { Text("· $it", style = MaterialTheme.typography.bodyExtraSmall) }
                    r.seconds?.let { Text("${it}s", style = MaterialTheme.typography.bodyExtraSmall) }
                }
            }
        }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center) } }
        if (digest.isNotEmpty()) {
            item {
                FilledTonalButton(onClick = { showDigest = !showDigest }, label = { Text("Digest (${digest.size})") },
                                  secondaryLabel = { Text("no rush: checks and news") }, modifier = Modifier.fillMaxWidth())
            }
            if (showDigest) for (c in digest) item { CardTile(c) { openCard = c } }
        }
        item { FilledTonalButton(onClick = typeQuestion, enabled = !busy && !listening, label = { Text("Type a question") },
                                 modifier = Modifier.fillMaxWidth()) }
        item {
            FilledTonalButton(onClick = { watching = !watching; pairing.watching = watching },
                              label = { Text(if (watching) "Approvals: on" else "Approvals: off") },
                              modifier = Modifier.fillMaxWidth())
        }
        item {
            OutlinedButton(onClick = {
                ApprovalService.stop(context)
                pairing.token = null
                onUnpaired()
            }, label = { Text("Unpair") }, modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun CardTile(c: Card, onClick: () -> Unit) {
    TitleCard(onClick = onClick, title = { Text(c.title) }, subtitle = { Text(c.role) }, modifier = Modifier.fillMaxWidth()) {
        Text(c.body, maxLines = 3)
    }
}

/** One card from a role, with its answers: what the owner taps goes back to that role (engram/herald.py). */
@Composable
private fun CardScreen(c: Card, pairing: Pairing, onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var error by remember { mutableStateOf<String?>(null) }
    BackHandler(onBack = onDone)

    fun answer(action: String) = scope.launch {
        try {
            pairing.request(context) { it.card(c.id, action) }
            Approvals.cards.value = Approvals.cards.value.filterNot { it.id == c.id }
            onDone()
        } catch (e: Exception) {
            error = e.message
        }
    }

    Screen {
        item { ListHeader { Text(c.title) } }
        item { Text(c.body, textAlign = TextAlign.Center) }
        item { Text("${c.role} · ${c.why}", style = MaterialTheme.typography.bodyExtraSmall, textAlign = TextAlign.Center) }
        for ((id, label) in c.actions) {
            item { Button(onClick = { answer(id) }, label = { Text(label) }, modifier = Modifier.fillMaxWidth()) }
        }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item { OutlinedButton(onClick = onDone, label = { Text("Back") }) }
    }
}

@Composable
private fun ApproveScreen(p: Pending, pairing: Pairing, onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var error by remember { mutableStateOf<String?>(null) }
    BackHandler(onBack = onDone)

    fun decide(approve: Boolean) = scope.launch {
        try {
            pairing.request(context) { it.decide(p.run, approve) }
            onDone()
        } catch (e: Exception) {
            error = e.message
        }
    }

    Screen {
        item { ListHeader { Text(p.headline ?: p.tool) } }
        item { Text(p.text, textAlign = TextAlign.Center) }
        item { Text("You asked: ${p.request}", style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center) }
        p.judge?.let { item { Text("Judge — $it", style = MaterialTheme.typography.bodyExtraSmall) } }
        item { Text("Effect: ${p.effect}", style = MaterialTheme.typography.bodyExtraSmall) }
        if (p.onWatch) {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Button(onClick = { decide(false) }, colors = ButtonDefaults.filledTonalButtonColors(),
                           icon = { Icon(painterResource(R.drawable.ic_close), contentDescription = "Deny") },
                           label = { Text("Deny") })
                    Button(onClick = { decide(true) },
                           icon = { Icon(painterResource(R.drawable.ic_check), contentDescription = "Approve") },
                           label = { Text("OK") })
                }
            }
        } else {
            item { Text("Destructive: decide on the laptop.", color = MaterialTheme.colorScheme.error,
                        textAlign = TextAlign.Center) }
        }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item { OutlinedButton(onClick = onDone, label = { Text("Back") }) }
    }
}

/** A scrolling screen with Wear's curved-edge list. */
@Composable
private fun Screen(content: androidx.wear.compose.foundation.lazy.ScalingLazyListScope.() -> Unit) {
    val state = rememberScalingLazyListState()
    ScreenScaffold(scrollState = state) { padding ->
        ScalingLazyColumn(state = state, contentPadding = padding, modifier = Modifier.fillMaxWidth(),
                          content = content)
    }
}

/** The system keyboard or voice input, for one line of text. */
@Composable
private fun textInput(label: String, onText: (String) -> Unit): () -> Unit {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        result.data?.let { RemoteInput.getResultsFromIntent(it)?.getCharSequence(label)?.toString() }
            ?.takeIf { it.isNotBlank() }?.let(onText)
    }
    return {
        val input = RemoteInput.Builder(label).setLabel(label)
            .wearableExtender { setEmojisAllowed(false); setInputActionType(EditorInfo.IME_ACTION_DONE) }.build()
        launcher.launch(RemoteInputIntentHelper.createActionRemoteInputIntent()
            .also { RemoteInputIntentHelper.putRemoteInputsExtra(it, listOf(input)) })
    }
}
