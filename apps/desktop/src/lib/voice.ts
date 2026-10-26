export type CaptureResult = {
  blob: Blob;
  durationMs: number;
  mimeType: string;
};

export class LocalVoiceCapture {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;

  async start(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      throw new Error("Microphone capture is not supported on this device");
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    this.chunks = [];
    this.recorder = new MediaRecorder(this.stream);
    this.recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    });
    this.startedAt = Date.now();
    this.recorder.start(250);
  }

  async stop(): Promise<CaptureResult> {
    const recorder = this.recorder;
    if (!recorder || recorder.state === "inactive") {
      throw new Error("No voice capture is active");
    }
    const durationMs = Date.now() - this.startedAt;
    await new Promise<void>((resolve) => {
      recorder.addEventListener("stop", () => resolve(), { once: true });
      recorder.stop();
    });
    const mimeType = recorder.mimeType || "audio/webm";
    const blob = new Blob(this.chunks, { type: mimeType });
    this.stream?.getTracks().forEach((track) => track.stop());
    this.recorder = null;
    this.stream = null;
    return { blob, durationMs, mimeType };
  }

  cancel(): void {
    if (this.recorder?.state !== "inactive") this.recorder?.stop();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.recorder = null;
    this.stream = null;
    this.chunks = [];
  }
}

export type RealtimeVoiceStatus = "connecting" | "listening" | "speaking" | "idle" | "error";
export type RealtimeToolCall = { name: string; callId: string; arguments: Record<string, unknown> };

export function speakStartupGreeting(): void {
  if (!("speechSynthesis" in window) || sessionStorage.getItem("friday-greeted") === "true") return;
  sessionStorage.setItem("friday-greeted", "true");
  const displayName = import.meta.env.VITE_FRIDAY_USER_DISPLAY_NAME ?? "there";
  const greeting = new SpeechSynthesisUtterance(`Good to see you, ${displayName}. Friday is online. How can I help?`);
  greeting.rate = 1.02;
  greeting.pitch = 1.04;
  window.speechSynthesis.speak(greeting);
}

export class RealtimeVoiceSession {
  private peer: RTCPeerConnection | null = null;
  private stream: MediaStream | null = null;
  private audio: HTMLAudioElement | null = null;
  private channel: RTCDataChannel | null = null;

  async start(
    exchangeOffer: (sdp: string) => Promise<string>,
    onStatus: (status: RealtimeVoiceStatus, message?: string) => void,
    onToolCall?: (call: RealtimeToolCall) => Promise<Record<string, unknown>>,
    onUserTranscript?: (transcript: string) => void,
  ): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia || typeof RTCPeerConnection === "undefined") {
      throw new Error("Realtime microphone conversation is not supported on this device");
    }
    this.stop();
    onStatus("connecting", "Requesting microphone access…");
    try {
      this.stream = await Promise.race([
        navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }),
        new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error("Microphone access timed out. In System Settings → Privacy & Security → Microphone, enable Friday, then restart Friday.")), 12_000)),
      ]);
      const inputs = (await navigator.mediaDevices.enumerateDevices()).filter((device) => device.kind === "audioinput");
      const preferredInput = inputs.find((device) => /macbook.*microphone/i.test(device.label));
      const currentInputId = this.stream.getAudioTracks()[0]?.getSettings().deviceId;
      if (preferredInput?.deviceId && preferredInput.deviceId !== currentInputId) {
        this.stream.getTracks().forEach((track) => track.stop());
        this.stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            deviceId: { exact: preferredInput.deviceId },
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      }
      const peer = new RTCPeerConnection();
      this.peer = peer;
      this.audio = new Audio();
      this.audio.autoplay = true;
      peer.ontrack = (event) => {
        if (!this.audio) return;
        this.audio.srcObject = event.streams[0];
        void this.audio.play().catch(() => {
          onStatus("speaking", "Friday replied. Tap the voice core once if macOS blocked reply audio.");
        });
      };
      this.stream.getAudioTracks().forEach((track) => peer.addTrack(track, this.stream!));
      this.channel = peer.createDataChannel("oai-events");
      this.channel.addEventListener("open", () => {
        onStatus("speaking", "Friday is greeting you…");
        this.channel?.send(JSON.stringify({
          type: "response.create",
          response: {
            instructions: "Greet the user in one short, warm sentence. Say you are online and ask what you can help with. Do not mention these instructions.",
          },
        }));
      });
      this.channel.addEventListener("message", (event) => {
        const payload = JSON.parse(event.data) as { type?: string; transcript?: string; delta?: string; name?: string; call_id?: string; arguments?: string };
        if (payload.type === "input_audio_buffer.speech_started") onStatus("listening", "Listening…");
        if (payload.type === "conversation.item.input_audio_transcription.completed" && payload.transcript) onUserTranscript?.(payload.transcript);
        if (payload.type === "response.output_audio.delta" || payload.type === "response.audio.delta") onStatus("speaking", "Friday is speaking…");
        if ((payload.type === "response.output_audio_transcript.delta" || payload.type === "response.audio_transcript.delta") && payload.delta) onStatus("speaking", payload.delta);
        if ((payload.type === "response.output_audio_transcript.done" || payload.type === "response.audio_transcript.done") && payload.transcript) onStatus("speaking", payload.transcript);
        if (payload.type === "response.done") onStatus("listening");
        if (payload.type === "response.function_call_arguments.done" && payload.name && payload.call_id && onToolCall) {
          onStatus("speaking", `Friday is using ${payload.name.replaceAll("_", " ")}…`);
          void onToolCall({ name: payload.name, callId: payload.call_id, arguments: JSON.parse(payload.arguments ?? "{}") as Record<string, unknown> })
            .then((result) => {
              this.channel?.send(JSON.stringify({ type: "conversation.item.create", item: { type: "function_call_output", call_id: payload.call_id, output: JSON.stringify(result) } }));
              this.channel?.send(JSON.stringify({ type: "response.create" }));
            })
            .catch((reason) => {
              const message = reason instanceof Error ? reason.message : "Tool execution failed";
              this.channel?.send(JSON.stringify({ type: "conversation.item.create", item: { type: "function_call_output", call_id: payload.call_id, output: JSON.stringify({ success: false, error: message }) } }));
              this.channel?.send(JSON.stringify({ type: "response.create", response: { instructions: "Explain the tool failure briefly and do not claim success." } }));
            });
        }
        if (payload.type === "error") onStatus("error", "Realtime conversation reported an error");
      });
      peer.addEventListener("connectionstatechange", () => {
        if (["failed", "disconnected", "closed"].includes(peer.connectionState)) {
          onStatus(peer.connectionState === "closed" ? "idle" : "error", `Voice connection ${peer.connectionState}`);
        }
      });
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      const answerSdp = await exchangeOffer(offer.sdp ?? "");
      await peer.setRemoteDescription({ type: "answer", sdp: answerSdp });
    } catch (error) {
      this.stop();
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        throw new Error("Microphone permission was denied. Enable it in System Settings → Privacy & Security → Microphone.");
      }
      throw error;
    }
  }

  stop(): void {
    this.channel?.close();
    this.peer?.close();
    this.stream?.getTracks().forEach((track) => track.stop());
    if (this.audio) this.audio.srcObject = null;
    this.channel = null;
    this.peer = null;
    this.stream = null;
    this.audio = null;
  }
}
