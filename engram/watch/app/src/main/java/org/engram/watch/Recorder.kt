package org.engram.watch

import android.Manifest
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.annotation.RequiresPermission
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.concurrent.thread

/**
 * Speech, captured only: 16 kHz mono 16-bit PCM, sent to the Mac as a WAV file and transcribed there, so no
 * recognizer on the watch (which may call a cloud service) ever hears it. At most [MAX_SECONDS] per clip.
 */
class Recorder {
    @Volatile private var record: AudioRecord? = null
    private var worker: Thread? = null
    private val pcm = ByteArrayOutputStream()

    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    fun start() {
        val min = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val r = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, RATE, AudioFormat.CHANNEL_IN_MONO,
                            AudioFormat.ENCODING_PCM_16BIT, maxOf(min, RATE / 5 * 2))
        pcm.reset()
        r.startRecording()
        record = r
        worker = thread(name = "recorder") {
            val buf = ByteArray(RATE / 10 * 2)
            while (record === r && pcm.size() < MAX_SECONDS * RATE * 2) {
                val n = r.read(buf, 0, buf.size)
                if (n <= 0) break
                pcm.write(buf, 0, n)
            }
        }
    }

    val recording get() = record != null

    /** Stops and returns the clip as a WAV file. */
    fun stop(): ByteArray {
        val r = record ?: return ByteArray(0)
        record = null
        worker?.join(1_000)
        r.stop()
        r.release()
        return wav(pcm.toByteArray())
    }

    private fun wav(data: ByteArray): ByteArray = ByteBuffer.allocate(44 + data.size).order(ByteOrder.LITTLE_ENDIAN)
        .put("RIFF".toByteArray()).putInt(36 + data.size).put("WAVE".toByteArray())
        .put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1).putInt(RATE).putInt(RATE * 2)
        .putShort(2).putShort(16)
        .put("data".toByteArray()).putInt(data.size).put(data)
        .array()

    companion object {
        const val RATE = 16_000
        const val MAX_SECONDS = 15
    }
}
