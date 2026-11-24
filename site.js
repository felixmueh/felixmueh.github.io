// Pause controls for looping clips (WCAG 2.2.2 "Pause, Stop, Hide") and
// reduced-motion handling. The only script on the site; no external requests.
//
// A clip is any element with the class "clip": either a real
//   <div class="clip"><video loop muted playsinline poster="…">…</video></div>
// or, until the real clips exist, a grey stand-in <div class="ph clip">.
//
// Real videos deliberately have no `autoplay` attribute: this script starts
// them, so without JS (or under prefers-reduced-motion) the poster stays and
// nothing moves without the visitor asking for it.

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

document.querySelectorAll('.clip').forEach((clip) => {
  const video = clip.querySelector('video');
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'pause';
  const clipName = (video ? video.getAttribute('aria-label') || video.title : clip.textContent).trim();
  clip.dataset.js = '';  // tells style.css that this script now owns the motion

  // One source of truth for "is it moving": the video's own state, or a class
  // on the stand-in that stops its CSS sweep.
  const isPlaying = () => (video ? !video.paused : !clip.classList.contains('paused'));
  const render = () => {
    const playing = isPlaying();
    btn.textContent = playing ? 'Pause' : 'Play';
    btn.setAttribute('aria-label', (playing ? 'Pause clip: ' : 'Play clip: ') + clipName);
  };

  if (video) {
    if (!reduceMotion) video.play().catch(() => {});  // autoplay may be blocked; the button still works
    video.addEventListener('play', render);
    video.addEventListener('pause', render);
  } else if (reduceMotion) {
    clip.classList.add('paused');
  }

  btn.addEventListener('click', () => {
    if (video) {
      if (video.paused) video.play(); else video.pause();
    } else {
      clip.classList.toggle('paused');
      render();
    }
  });

  render();
  clip.appendChild(btn);
});
