"""
livecam.py - the browser-camera component for the Live camera tab.

WHY NOT WEBRTC: streaming video to the server over WebRTC needs a relay (TURN) server on many
networks, and failed on Streamlit Community Cloud ("connection failed") without one. This
component needs no relay: it sends small snapshots over the app's normal connection instead.

HOW IT WORKS
  browser (JavaScript, below)                         server (Python, live.py)
  ---------------------------                         ------------------------
  shows the camera, smoothly, locally
  every ~0.2 s: grab a 640 px JPEG  ---------------->  read_gauge() on it: the SAME pipeline as
                                                        everywhere else in the app
  draws the dial circle, pivot, needle  <------------  sends back the geometry + reading
  and the reading ON TOP of the video

A new snapshot is only sent once the previous one has been answered, so a slow server never
builds up a queue. The video is processed in memory and not stored.
"""

import streamlit as st

HTML = """
<div class="cam">
  <div class="stage">
    <video playsinline muted autoplay></video>
    <canvas></canvas>
    <div class="msg">Press Start camera.</div>
  </div>
  <div class="bar">
    <button class="go" type="button">Start camera</button>
    <select class="dev" title="Choose camera" hidden></select>
  </div>
</div>
"""

CSS = """
.cam { font-family: 'DM Sans', system-ui, sans-serif; }
.stage { position: relative; width: 100%; aspect-ratio: 4 / 3; background: #1A2922; border-radius: 4px; overflow: hidden;
         box-shadow: inset 0 0 0 1px rgba(0,0,0,.5); }
video, canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
video { object-fit: fill; }
canvas { pointer-events: none; }
.msg { position: absolute; left: 0; right: 0; top: 50%; transform: translateY(-50%); text-align: center; padding: 0 1.5rem;
       color: #CDB98F; font-size: .95rem; line-height: 1.45; }
.msg:empty { display: none; }
.bar { display: flex; gap: .6rem; align-items: center; margin-top: .7rem; }
.go { background: #7A1F1F; color: #FBF5E9; border: 0; border-radius: 3px; padding: .55rem 1.1rem; font: 600 .9rem 'DM Sans', sans-serif;
      letter-spacing: .02em; cursor: pointer; box-shadow: 0 2px 0 #4a1010, 0 8px 14px -8px rgba(122,31,31,.7);
      transition: transform .15s, box-shadow .2s; }
.go:hover { transform: translateY(-2px); box-shadow: 0 4px 0 #4a1010, 0 14px 18px -8px rgba(122,31,31,.7); }
.go:active { transform: translateY(1px); box-shadow: inset 0 2px 4px rgba(0,0,0,.4); }
.go.on { background: #24392F; box-shadow: 0 2px 0 #131f19, 0 8px 14px -8px rgba(36,57,47,.7); }
.dev { flex: 1; min-width: 0; background: #FBF5E9; border: 1px solid #CDB98F; border-radius: 3px; padding: .5rem; color: #2B261F;
       font: .85rem 'DM Sans', sans-serif; }
"""

JS = """
export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const root = parentElement;                       // a ShadowRoot (styles are isolated)
  let G = root.__gd;

  if (!G) {                                         // first call only: set everything up once
    G = root.__gd = { stream: null, seq: 0, ack: 0, sentAt: 0, data: null, setStateValue: null };
    const q = (s) => root.querySelector(s);
    G.video = q('video'); G.canvas = q('canvas'); G.msg = q('.msg'); G.go = q('.go'); G.sel = q('.dev');
    G.grab = document.createElement('canvas');      // off-screen canvas used to shrink each frame
    G.host = root.host || root;

    G.say = (t) => { G.msg.textContent = t || ''; };

    G.draw = () => {                                // dial circle, pivot, needle and reading over the video
      const c = G.canvas, ctx = c.getContext('2d');
      const w = c.clientWidth, h = c.clientHeight, dpr = window.devicePixelRatio || 1;
      if (c.width !== Math.round(w * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const d = G.data;
      if (!G.stream || !d || !d.dial) return;
      const s = w / d.w;
      const rim = d.rim || d.dial;
      ctx.lineCap = 'round';
      ctx.strokeStyle = '#B08D57'; ctx.lineWidth = 3;                 // the dial the app found
      ctx.beginPath(); ctx.arc(rim[0] * s, rim[1] * s, rim[2] * s, 0, 2 * Math.PI); ctx.stroke();
      if (d.tip) {                                                    // the needle it is reading
        ctx.strokeStyle = 'rgba(0,0,0,.45)'; ctx.lineWidth = 7;
        ctx.beginPath(); ctx.moveTo(d.dial[0] * s, d.dial[1] * s); ctx.lineTo(d.tip[0] * s, d.tip[1] * s); ctx.stroke();
        ctx.strokeStyle = '#E04A3C'; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.moveTo(d.dial[0] * s, d.dial[1] * s); ctx.lineTo(d.tip[0] * s, d.tip[1] * s); ctx.stroke();
      }
      ctx.fillStyle = '#B08D57'; ctx.beginPath(); ctx.arc(d.dial[0] * s, d.dial[1] * s, 6, 0, 2 * Math.PI); ctx.fill();
      if (d.text) {                                                   // the reading, in its status colour
        ctx.font = '600 22px "DM Mono", monospace';
        const tw = ctx.measureText(d.text).width;
        ctx.fillStyle = 'rgba(20,30,25,.82)'; ctx.fillRect(10, 10, tw + 22, 38);
        ctx.fillStyle = d.colour || '#F4EBD9'; ctx.fillText(d.text, 21, 37);
      }
    };

    G.stop = (tell) => {
      if (G.stream) { G.stream.getTracks().forEach((t) => t.stop()); }
      G.stream = null; G.video.srcObject = null; G.seq = 0; G.ack = 0;
      G.go.textContent = 'Start camera'; G.go.classList.remove('on');
      G.draw();
      if (tell && G.setStateValue) G.setStateValue('running', false);
    };

    G.start = async (deviceId) => {
      G.stop(false);
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        G.say('This browser cannot open the camera here. The page must be opened over https (or localhost).'); return;
      }
      G.say('Waiting for camera permission…');
      const size = { width: { ideal: 640 }, height: { ideal: 480 } };
      const video = deviceId ? { deviceId: { exact: deviceId }, ...size } : { facingMode: { ideal: 'environment' }, ...size };
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
        G.stream = stream; G.video.srcObject = stream; await G.video.play();
        const settings = stream.getVideoTracks()[0].getSettings();
        if (settings.width && settings.height) G.canvas.parentElement.style.aspectRatio = settings.width + ' / ' + settings.height;
        const devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
        if (devs.length > 1) {
          G.sel.innerHTML = devs.map((d, i) => '<option value="' + d.deviceId + '">' + (d.label || 'Camera ' + (i + 1)) + '</option>').join('');
          G.sel.value = settings.deviceId || devs[0].deviceId; G.sel.hidden = false;
        }
        G.say(''); G.go.textContent = 'Stop camera'; G.go.classList.add('on');
        G.setStateValue('running', true);
      } catch (e) {
        const name = (e && e.name) || '';
        G.say(name === 'NotAllowedError' ? 'Camera access was blocked. Allow the camera for this site in your browser settings, then press Start camera again.'
            : name === 'NotFoundError' ? 'No camera was found on this device.'
            : name === 'NotReadableError' ? 'The camera is in use by another app. Close it and try again.'
            : 'Could not start the camera (' + (name || e) + ').');
        G.stop(true);
      }
    };

    G.tick = () => {                                // runs 10x a second: send the next snapshot when the last one is answered
      if (!G.host.isConnected) {                    // the component was removed (tab changed): switch the camera off
        clearInterval(G.timer); G.stop(false); root.__gd = null; return;
      }
      const v = G.video;
      if (!G.stream || v.readyState < 2 || !v.videoWidth) return;
      const now = performance.now();
      if (G.seq !== G.ack && now - G.sentAt < 3000) return;
      const W = 640, H = Math.round(W * v.videoHeight / v.videoWidth);
      G.grab.width = W; G.grab.height = H;
      G.grab.getContext('2d').drawImage(v, 0, 0, W, H);
      const url = G.grab.toDataURL('image/jpeg', 0.72);
      G.seq += 1; G.sentAt = now;
      G.setStateValue('frame', { seq: G.seq, w: W, h: H, jpeg: url.slice(url.indexOf(',') + 1) });
    };

    G.go.onclick = () => (G.stream ? G.stop(true) : G.start());
    G.sel.onchange = () => G.start(G.sel.value);
    new ResizeObserver(() => G.draw()).observe(G.canvas);
    G.timer = setInterval(G.tick, 100);
  }

  G.setStateValue = setStateValue;                  // every call: remember the newest data and callback
  G.data = data;
  if (data && data.ack !== undefined && data.ack !== null) G.ack = data.ack;
  G.draw();
}
"""

camera = st.components.v2.component("gauge_camera", html=HTML, css=CSS, js=JS)
