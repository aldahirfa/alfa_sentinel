// Tono discreto para las alertas flotantes globales (sección 15 de la
// especificación "Alertas flotantes globales de alta prioridad",
// 2026-08-17, ver PENDIENTES.md): "no utilizar sonidos agresivos o
// repetitivos". Se genera con Web Audio API en vez de un archivo de
// audio -- nada que descargar/alojar, y el volumen/duración quedan
// bajo control exacto acá mismo.
//
// Los navegadores bloquean autoplay de audio hasta que hubo una
// interacción real del usuario con la página -- el AudioContext se
// crea recién al necesitarse (no en el import), y si sigue
// "suspended" (todavía no hubo esa interacción), se intenta resumir
// una vez y si no se puede, se descarta en silencio: el sonido es un
// complemento opcional (sección 15), nunca algo de lo que dependa la
// notificación visual para cumplir su función.

let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx) return null;
  if (!ctx) ctx = new AudioCtx();
  return ctx;
}

function tone(context: AudioContext, frequency: number, startAt: number, duration: number, peakGain: number) {
  const osc = context.createOscillator();
  const gain = context.createGain();
  osc.type = "sine";
  osc.frequency.value = frequency;

  // Fade-in/out corto para que no truene el "click" de encender/apagar
  // un oscilador de golpe -- lo que hace que sea "discreto" en vez de
  // un pitido crudo.
  gain.gain.setValueAtTime(0, startAt);
  gain.gain.linearRampToValueAtTime(peakGain, startAt + 0.02);
  gain.gain.linearRampToValueAtTime(0, startAt + duration);

  osc.connect(gain);
  gain.connect(context.destination);
  osc.start(startAt);
  osc.stop(startAt + duration + 0.02);
}

/** Un solo tono suave -- para ALTO (sección 15: "puede existir una
 * señal sonora discreta"). */
function playAltoChime(context: AudioContext) {
  const now = context.currentTime;
  tone(context, 660, now, 0.16, 0.05);
}

/** Dos tonos cortos ascendentes -- para CRÍTICO, ligeramente más
 * presente que ALTO (más prioridad visual/sonora, sección 3), pero
 * siempre corto y sin repetirse (nunca un bucle). */
function playCriticoChime(context: AudioContext) {
  const now = context.currentTime;
  tone(context, 660, now, 0.14, 0.06);
  tone(context, 880, now + 0.12, 0.18, 0.07);
}

export function playAlertSound(severity: "ALTO" | "CRÍTICO") {
  try {
    const context = getContext();
    if (!context) return;

    const afterResume = () => {
      if (severity === "CRÍTICO") playCriticoChime(context);
      else playAltoChime(context);
    };

    if (context.state === "suspended") {
      context.resume().then(afterResume).catch(() => {});
    } else {
      afterResume();
    }
  } catch {
    // El sonido es un complemento opcional -- un fallo acá nunca debe
    // interrumpir la notificación visual real.
  }
}
