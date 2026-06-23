/**
 * Storm Risk Card
 *
 * A self-contained Lovelace card for the Storm Risk integration. It needs only
 * the Storm Risk score sensor: the score breakdown (cape_score / cin_score /
 * dp_score), the interpretation level, and the 24h forecast all live in that
 * one entity's attributes.
 *
 * The headline number is a 0-100 "ingredients" score (how loaded the
 * atmosphere is), NOT a probability of a storm.
 *
 * Vanilla custom element -- no build step, no external dependencies.
 */

const LEVELS = {
  none: { label: "None", color: "#43a047" },
  quiet: { label: "Quiet", color: "#7cb342" },
  watch: { label: "Watch", color: "#fdd835" },
  loaded: { label: "Loaded", color: "#fb8c00" },
  severe: { label: "Severe", color: "#e53935" },
};

// Storm-organisation modes (derived from wind shear) shown in the context line.
const MODES = {
  pulse: "Pulse storms",
  organised: "Organised",
  supercell: "Supercell potential",
};

// Cap state (from CIN) — whether the lid can break. Shown in the context line.
const CAP_STATES = {
  locked: "Locked",
  loadable: "Loadable",
  unlocked: "Cap open",
};

// CAPE magnitude label, capitalised, for under the CAPE bar.
const CAPE_MAGNITUDES = {
  weak: "Weak",
  moderate: "Moderate",
  significant: "Significant",
  major: "Major",
  extreme: "Extreme",
};

// CIN trajectory (arrow keyed to cap direction). Paired with the cap state on
// the CIN bar, so kept short here.
const CIN_TRENDS = {
  strengthening: "strengthening ↑",
  holding: "steady →",
  weakening: "weakening ↓",
};

// Trigger type, appended to the trigger chip (e.g. "trigger 40% · diurnal").
const TRIGGER_SOURCES = {
  none: "none visible",
  diurnal: "diurnal",
  synoptic: "synoptic",
};

const INGREDIENTS = [
  {
    key: "cape_score",
    raw: "cape",
    unit: "J/kg",
    digits: 0,
    label: "CAPE",
    title: "Instability / fuel",
    tip: "CAPE — Convective Available Potential Energy. The fuel for storms: how much energy is available to lift air. The higher it is, the taller and more vigorous storms can grow.",
  },
  {
    key: "cin_score",
    raw: "cin",
    unit: "J/kg",
    digits: 0,
    label: "CIN",
    title: "Lid (gated by CAPE)",
    tip: "CIN — Convective Inhibition, the “lid”. This bar is fuller when the lid is WEAK (storms fire easily) and near-empty when the cap is strong — a strong cap reads as Locked here (energy stored, not yet released), which is correct, not a glitch. Only counts when there's CAPE for it to act on.",
  },
  {
    key: "dp_score",
    raw: "dew_point",
    unit: "&deg;C",
    digits: 1,
    label: "Dew pt",
    title: "Low-level moisture",
    tip: "Dew point — low-level moisture. Humid air (a high dew point) feeds storms. It's gated by CAPE here, so a muggy but stable day doesn't over-score on moisture alone.",
  },
];

// Each ingredient contributes up to 33 points.
const SCORE_CAP = 33;

class StormRiskCard extends HTMLElement {
  setConfig(config) {
    // Don't throw on a missing entity: a bare throw renders HA's cryptic
    // "Configuration Error" box. Store the config and let _render() show a
    // clear, actionable hint instead.
    this._config = {
      name: "Storm Risk",
      show_breakdown: true,
      show_forecast: true,
      ...(config || {}),
    };
    this._root = this._root || this.attachShadow({ mode: "open" });
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig(hass) {
    // The entity id depends on the location name (e.g. sensor.home_storm_risk),
    // so find a real Storm Risk score sensor on this system rather than guess.
    // Match "<something>_storm_risk" but not "..._storm_risk_outlook".
    const ids = hass ? Object.keys(hass.states) : [];
    const match = ids.find((id) => /^sensor\..+_storm_risk$/.test(id));
    return { entity: match || "sensor.home_storm_risk" };
  }

  _render() {
    if (!this._config) return;
    const entityId = this._config.entity;
    if (!entityId) {
      this._root.innerHTML = `
        ${this._styles()}
        <ha-card header="Storm Risk">
          <div class="warn">Set <code>entity:</code> to your Storm Risk
          sensor — e.g. <code>sensor.home_storm_risk</code>
          (check Settings → Devices &amp; services → Storm Risk for the id).</div>
        </ha-card>`;
      return;
    }
    if (!this._hass) return;
    const stateObj = this._hass.states[entityId];

    if (!stateObj) {
      this._root.innerHTML = `
        ${this._styles()}
        <ha-card header="${this._config.name}">
          <div class="warn">Entity <code>${entityId}</code> not found.</div>
        </ha-card>`;
      return;
    }

    const unavailable =
      stateObj.state === "unavailable" || stateObj.state === "unknown";
    const risk = unavailable ? 0 : Math.round(Number(stateObj.state));
    const attrs = stateObj.attributes || {};
    const level = LEVELS[attrs.level] || LEVELS.none;
    const color = unavailable ? "var(--disabled-text-color)" : level.color;

    this._root.innerHTML = `
      ${this._styles()}
      <ha-card>
        <div class="header">
          <div class="title">${this._config.name}</div>
          <div class="level" style="color:${color}">
            ${unavailable ? "Unavailable" : level.label}
          </div>
        </div>
        ${unavailable ? "" : this._context(attrs)}
        <div class="body">
          ${this._gauge(risk, color, unavailable)}
          ${
            this._config.show_breakdown && !unavailable
              ? this._breakdown(attrs)
              : ""
          }
        </div>
        ${
          this._config.show_forecast && !unavailable
            ? this._forecast(attrs.forecast || [], color)
            : ""
        }
      </ha-card>`;
  }

  _context(attrs) {
    // A compact "organisation · shear · trigger" line. Each part is only
    // shown when the data is present, so models without shear/precip data
    // just show fewer chips (or none).
    const parts = [];
    if (attrs.roaming) {
      parts.push(
        `📍 ${attrs.location_source || "Roaming"}`
      );
    }
    // (Cap state now lives on the CIN bar, where it explains that bar.)
    const mode = MODES[attrs.mode];
    if (mode) parts.push(mode);
    if (attrs.shear !== undefined && attrs.shear !== null) {
      parts.push(`shear ${Number(attrs.shear).toFixed(0)} m/s`);
    }
    if (attrs.trigger !== undefined && attrs.trigger !== null) {
      const src = TRIGGER_SOURCES[attrs.trigger_source];
      parts.push(
        `trigger ${Number(attrs.trigger).toFixed(0)}%${src ? ` ${src}` : ""}`
      );
    }
    if (!parts.length) return "";
    return `<div class="context">${parts.join(" &middot; ")}</div>`;
  }

  _gauge(risk, color, unavailable) {
    // 220-degree sweep ring gauge. Circumference of the radius-52 circle ~327.
    const r = 52;
    const circ = 2 * Math.PI * r;
    const sweep = 220 / 360; // visible portion of the ring
    const frac = Math.max(0, Math.min(100, risk)) / 100;
    const track = circ * sweep;
    const fill = track * frac;
    const rotate = 90 + (360 - 220) / 2; // centre the gap at the bottom
    return `
      <div class="gauge tip" tabindex="0"
        aria-label="Storm risk ingredients score, 0 to 100">
        <svg viewBox="0 0 120 120">
          <circle class="track" cx="60" cy="60" r="${r}"
            stroke-dasharray="${track} ${circ}"
            transform="rotate(${rotate} 60 60)"></circle>
          <circle cx="60" cy="60" r="${r}" stroke="${color}"
            stroke-dasharray="${fill} ${circ}"
            transform="rotate(${rotate} 60 60)"></circle>
        </svg>
        <div class="value" style="color:${color}">
          <span class="value-inner"><span class="num">${
            unavailable ? "-" : risk
          }</span><span class="suffix">/100</span></span>
        </div>
        <span class="tip-bubble below" role="tooltip">
          A 0–100 <b>ingredients score</b> — how loaded the atmosphere is for
          storms, from instability (CAPE), the lid (CIN) and moisture. It's
          <b>not</b> a probability that a storm will happen.
        </span>
      </div>`;
  }

  _breakdown(attrs) {
    const rows = INGREDIENTS.map((ing) => {
      const score = Number(attrs[ing.key] ?? 0);
      const pct = Math.max(0, Math.min(100, (score / SCORE_CAP) * 100));
      const raw = attrs[ing.raw];
      let sub =
        raw === undefined || raw === null
          ? ""
          : `${Number(raw).toFixed(ing.digits)} ${ing.unit}`;
      // Extra context the bar can't show: how maxed the CAPE really is (since
      // it saturates near 1000 J/kg), and which way the cap is trending.
      if (sub) {
        if (ing.key === "cape_score" && CAPE_MAGNITUDES[attrs.cape_magnitude]) {
          sub += ` &middot; ${CAPE_MAGNITUDES[attrs.cape_magnitude]}`;
        } else if (ing.key === "cin_score") {
          // Cap state explains why a strong (very negative) CIN reads low here;
          // the trend says which way it's heading.
          const bits = [CAP_STATES[attrs.cap_state], CIN_TRENDS[attrs.cin_trend]]
            .filter(Boolean)
            .join(", ");
          if (bits) sub += ` &middot; ${bits}`;
        }
      }
      return `
        <div class="bar-group">
          <div class="bar-row">
            <span class="bar-label tip" tabindex="0" aria-label="${ing.label}: ${ing.title}">
              ${ing.label}
              <span class="tip-bubble" role="tooltip">${ing.tip}</span>
            </span>
            <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
            <span class="bar-val">${score.toFixed(0)}<span class="bar-cap">/${SCORE_CAP}</span></span>
          </div>
          <div class="bar-sub">${sub}</div>
        </div>`;
    }).join("");
    return `<div class="breakdown">${rows}</div>`;
  }

  _forecast(forecast, color) {
    if (!Array.isArray(forecast) || forecast.length < 2) return "";
    const w = 300;
    const h = 84;
    const pad = 4;
    const n = forecast.length;
    const num = (v) => Number(v) || 0;
    const xOf = (i) => pad + (i * (w - 2 * pad)) / (n - 1);
    // y for a 0-100 stacked total; each component is 0-33, three stack to ~99.
    const yOf = (v) =>
      h - pad - (Math.max(0, Math.min(100, v)) / 100) * (h - 2 * pad);

    // Cumulative stack boundaries per hour: 0, CAPE, CAPE+CIN, CAPE+CIN+Dew.
    const cape = forecast.map((p) => num(p.cape_score));
    const cin = forecast.map((p) => num(p.cin_score));
    const dp = forecast.map((p) => num(p.dp_score));
    const c1 = cape;
    const c2 = cape.map((v, i) => v + cin[i]);
    const c3 = cape.map((v, i) => v + cin[i] + dp[i]);

    const band = (lower, upper, cls) => {
      const up = forecast.map((_, i) => `${xOf(i).toFixed(1)},${yOf(upper[i]).toFixed(1)}`);
      const lo = forecast
        .map((_, i) => `${xOf(i).toFixed(1)},${yOf(lower[i]).toFixed(1)}`)
        .reverse();
      return `<polygon class="${cls}" points="${up.concat(lo).join(" ")}"></polygon>`;
    };
    const bands =
      band(forecast.map(() => 0), c1, "band-cape") +
      band(c1, c2, "band-cin") +
      band(c2, c3, "band-dp");
    // Total outline on top of the stack.
    const topLine = forecast
      .map((_, i) => `${xOf(i).toFixed(1)},${yOf(c3[i]).toFixed(1)}`)
      .join(" ");

    const first = forecast[0].datetime?.slice(11, 16) ?? "";
    const last = forecast[n - 1].datetime?.slice(11, 16) ?? "";

    // Peak hour of the total score -> dot + label on the top of the stack.
    let peak = 0;
    for (let i = 1; i < n; i++) {
      if (num(forecast[i].storm_risk) > num(forecast[peak].storm_risk)) peak = i;
    }
    const peakVal = Math.round(Math.max(0, Math.min(100, num(forecast[peak].storm_risk))));
    const peakTime = forecast[peak].datetime?.slice(11, 16) ?? "";
    const peakLeft = (xOf(peak) / w) * 100;
    const peakTop = yOf(c3[peak]);
    const labelLeft = Math.max(16, Math.min(84, peakLeft));
    const labelTop = peakTop > 18 ? peakTop - 18 : peakTop + 7;

    return `
      <div class="forecast">
        <div class="forecast-head">
          <span class="forecast-title tip" tabindex="0"
            aria-label="Next ${n} hour ingredient mix forecast">
            Next ${n}h ingredient mix
            <span class="tip-bubble" role="tooltip">
              The score split into its ingredients each hour — CAPE, CIN and dew
              point stack to the total (0–100). The dot marks the forecast
              <b>peak</b> (time and score).
            </span>
          </span>
          <span class="legend">
            <span class="key"><i class="band-cape"></i>CAPE</span>
            <span class="key"><i class="band-cin"></i>CIN</span>
            <span class="key"><i class="band-dp"></i>Dew</span>
          </span>
        </div>
        <div class="spark-wrap">
          <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
            ${bands}
            <polyline class="spark-line" points="${topLine}"></polyline>
          </svg>
          <span class="peak-dot" style="left:${peakLeft.toFixed(1)}%; top:${peakTop.toFixed(1)}px; background:${color}"></span>
          <span class="peak-label"
            style="left:${labelLeft.toFixed(1)}%; top:${labelTop.toFixed(1)}px; color:${color}">
            ${peakTime} &middot; ${peakVal}/100
          </span>
        </div>
        <div class="forecast-axis"><span>${first}</span><span>${last}</span></div>
      </div>`;
  }

  _styles() {
    return `
      <style>
        ha-card { padding: 16px; }
        .header {
          display: flex; justify-content: space-between; align-items: baseline;
          margin-bottom: 4px;
        }
        .title { font-size: 1.1rem; font-weight: 500; color: var(--primary-text-color); }
        .level { font-size: 0.9rem; font-weight: 500; }
        .context {
          font-size: 0.78rem; color: var(--secondary-text-color);
          margin: -2px 0 8px;
        }
        .body { display: flex; align-items: center; gap: 16px; }
        .gauge { position: relative; width: 120px; height: 120px; flex: 0 0 auto; }
        .gauge svg { width: 100%; height: 100%; }
        .gauge circle {
          fill: none; stroke-width: 10; stroke-linecap: round;
          transition: stroke-dasharray 0.6s ease;
        }
        .gauge circle.track { stroke: var(--divider-color, #e0e0e0); }
        .value {
          position: absolute; inset: 0;
          display: flex; align-items: center; justify-content: center;
        }
        .value-inner { line-height: 1; white-space: nowrap; }
        .value .num { font-size: 2.2rem; font-weight: 600; }
        .value .suffix { font-size: 0.85rem; font-weight: 500; opacity: 0.7; margin-left: 1px; }
        .breakdown { flex: 1 1 auto; display: flex; flex-direction: column; gap: 10px; }
        .bar-group { display: flex; flex-direction: column; }
        .bar-row { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }
        .bar-sub {
          margin-left: 56px; margin-top: 2px;
          font-size: 0.72rem; color: var(--secondary-text-color);
        }
        .bar-label { width: 48px; color: var(--secondary-text-color); }
        /* Hoverable help tooltips (ingredient labels, gauge, forecast). */
        .tip { position: relative; cursor: help; outline: none; }
        .bar-label.tip, .forecast-title.tip {
          border-bottom: 1px dotted var(--secondary-text-color);
        }
        /* Shrink the underline to hug the title text, not the full row. */
        .forecast-title.tip { display: inline-block; }
        .tip-bubble {
          position: absolute; left: 0; bottom: calc(100% + 8px);
          width: 220px; padding: 8px 10px; box-sizing: border-box;
          border-radius: 8px;
          background: var(--ha-card-background, var(--card-background-color, #fff));
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color, #e0e0e0);
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28);
          font-size: 0.72rem; font-weight: 400; line-height: 1.4;
          white-space: normal; text-align: left;
          opacity: 0; visibility: hidden;
          transition: opacity 0.15s ease;
          z-index: 9; pointer-events: none;
        }
        /* Placement modifiers. */
        .tip-bubble.below { top: calc(100% + 8px); bottom: auto; }
        .tip-bubble.center { left: 50%; transform: translateX(-50%); }
        .tip:hover .tip-bubble,
        .tip:focus .tip-bubble,
        .tip:focus-visible .tip-bubble {
          opacity: 1; visibility: visible;
        }
        .bar-track {
          flex: 1; height: 8px; border-radius: 4px;
          background: var(--divider-color, #e0e0e0); overflow: hidden;
        }
        .bar-fill {
          display: block; height: 100%; border-radius: 4px;
          background: var(--primary-color); transition: width 0.6s ease;
        }
        .bar-val { width: 46px; text-align: right; color: var(--primary-text-color); }
        .bar-cap { color: var(--secondary-text-color); font-size: 0.75rem; }
        .forecast { margin-top: 14px; }
        .forecast-head {
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 3px;
        }
        .forecast-title { font-size: 0.8rem; color: var(--secondary-text-color); }
        .legend { display: flex; gap: 10px; font-size: 0.7rem;
          color: var(--secondary-text-color); }
        .legend .key { display: inline-flex; align-items: center; gap: 4px; }
        .legend i {
          width: 9px; height: 9px; border-radius: 2px; display: inline-block;
        }
        .spark-wrap { position: relative; }
        .forecast svg { width: 100%; height: 84px; display: block; }
        .peak-dot {
          position: absolute; width: 7px; height: 7px; border-radius: 50%;
          transform: translate(-50%, -50%);
          box-shadow: 0 0 0 2px var(--card-background-color, #fff);
          pointer-events: none;
        }
        .peak-label {
          position: absolute; transform: translateX(-50%);
          font-size: 0.7rem; font-weight: 600; white-space: nowrap;
          pointer-events: none;
        }
        .spark-line {
          fill: none; stroke: var(--primary-text-color); stroke-width: 1.5;
          opacity: 0.55; vector-effect: non-scaling-stroke;
        }
        /* Stacked ingredient bands: fuel / lid / moisture. */
        .band-cape, .legend i.band-cape { fill: #ef6c00; background: #ef6c00; }
        .band-cin, .legend i.band-cin { fill: #5c6bc0; background: #5c6bc0; }
        .band-dp, .legend i.band-dp { fill: #26a69a; background: #26a69a; }
        .band-cape, .band-cin, .band-dp { opacity: 0.85; }
        .forecast-axis {
          display: flex; justify-content: space-between;
          font-size: 0.7rem; color: var(--secondary-text-color);
        }
        .warn { color: var(--error-color); padding: 8px 0; }
      </style>`;
  }
}

// Hail favourability -> label + colour for the dynamics card.
const HAIL_LEVELS = {
  unlikely: { label: "Unlikely", color: "#43a047" },
  possible: { label: "Possible", color: "#fb8c00" },
  favourable: { label: "Favourable", color: "#e53935" },
  unknown: { label: "Unknown", color: "var(--disabled-text-color)" },
};

/**
 * Storm Dynamics card — a companion to the main Storm Risk card focused on
 * *where* and *what kind*: the deep-layer steering motion (where storms would
 * track, for hit/miss reasoning) and a hail-favourability read-out. Reads the
 * same Storm Risk sensor's attributes.
 */
class StormDynamicsCard extends HTMLElement {
  setConfig(config) {
    this._config = {
      name: "Storm Dynamics",
      ...(config || {}),
    };
    this._root = this._root || this.attachShadow({ mode: "open" });
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig(hass) {
    const ids = hass ? Object.keys(hass.states) : [];
    const match = ids.find((id) => /^sensor\..+_storm_risk$/.test(id));
    return { entity: match || "sensor.home_storm_risk" };
  }

  _render() {
    if (!this._config) return;
    const entityId = this._config.entity;
    if (!entityId) {
      this._root.innerHTML = `${this._styles()}
        <ha-card header="Storm Dynamics"><div class="warn">Set
        <code>entity:</code> to your Storm Risk sensor — e.g.
        <code>sensor.home_storm_risk</code>.</div></ha-card>`;
      return;
    }
    if (!this._hass) return;
    const s = this._hass.states[entityId];
    if (!s) {
      this._root.innerHTML = `${this._styles()}
        <ha-card header="${this._config.name}"><div class="warn">Entity
        <code>${entityId}</code> not found.</div></ha-card>`;
      return;
    }
    const a = s.attributes || {};
    const unavailable = s.state === "unavailable" || s.state === "unknown";

    this._root.innerHTML = `
      ${this._styles()}
      <ha-card>
        <div class="title">${this._config.name}</div>
        ${unavailable ? `<div class="warn">Unavailable</div>` : `
          <div class="grid">
            ${this._motion(a)}
            ${this._hail(a)}
          </div>`}
      </ha-card>`;
  }

  _motion(a) {
    const dir = a.storm_motion_dir;
    const has = dir !== undefined && dir !== null;
    const speed = a.storm_motion_speed;
    const cardinal = a.storm_motion_cardinal || "";
    const sub = has
      ? `Toward ${cardinal}${
          speed != null ? ` · ${Number(speed).toFixed(0)} m/s` : ""
        }`
      : "No steering data";
    const arrow = has
      ? `<g transform="rotate(${Number(dir)} 50 50)">
           <line x1="50" y1="52" x2="50" y2="20" class="needle"></line>
           <polygon points="50,12 44,26 56,26" class="needle"></polygon>
         </g>`
      : "";
    return `
      <div class="panel">
        <div class="panel-title tip">Storm motion
          <span class="tip-bubble" role="tooltip">Approximate direction storms
          would track, from the deep-layer (700–300 hPa) mean wind. Single cells
          follow this; <b>supercells deviate</b>. Not exact motion.</span>
        </div>
        <svg viewBox="0 0 100 100" class="compass">
          <circle cx="50" cy="50" r="42" class="dial"></circle>
          <text x="50" y="14" class="rose">N</text>
          <text x="89" y="53" class="rose">E</text>
          <text x="50" y="92" class="rose">S</text>
          <text x="11" y="53" class="rose">W</text>
          ${arrow}
          <circle cx="50" cy="50" r="3" class="hub"></circle>
        </svg>
        <div class="panel-sub">${sub}</div>
      </div>`;
  }

  _hail(a) {
    const hail = HAIL_LEVELS[a.hail] || HAIL_LEVELS.unknown;
    const factors = [];
    if (a.cape != null) {
      const mag = CAPE_MAGNITUDES[a.cape_magnitude];
      factors.push(`CAPE ${Number(a.cape).toFixed(0)}${mag ? ` (${mag})` : ""}`);
    }
    if (a.freezing_level != null) {
      factors.push(`freezing ${Number(a.freezing_level).toFixed(0)} m`);
    }
    if (a.shear != null) factors.push(`shear ${Number(a.shear).toFixed(0)} m/s`);
    return `
      <div class="panel">
        <div class="panel-title tip">Hail
          <span class="tip-bubble" role="tooltip">Favourability (not a
          probability) from strong updraft (CAPE ≥ 1500), cold air aloft
          (freezing level &lt; 3500 m) and shear (≥ 10 m/s).</span>
        </div>
        <div class="hail-badge" style="color:${hail.color}">
          <span class="hail-dot" style="background:${hail.color}"></span>
          ${hail.label}
        </div>
        <div class="panel-sub">${factors.join(" · ") || "—"}</div>
      </div>`;
  }

  _styles() {
    return `
      <style>
        ha-card { padding: 16px; }
        .title { font-size: 1.1rem; font-weight: 500; margin-bottom: 10px;
          color: var(--primary-text-color); }
        .grid { display: flex; gap: 16px; }
        .panel { flex: 1 1 0; display: flex; flex-direction: column;
          align-items: center; text-align: center; gap: 6px; }
        .panel-title { font-size: 0.85rem; color: var(--secondary-text-color);
          position: relative; cursor: help;
          border-bottom: 1px dotted var(--secondary-text-color); }
        .panel-sub { font-size: 0.78rem; color: var(--secondary-text-color); }
        .compass { width: 96px; height: 96px; }
        .compass .dial { fill: none; stroke: var(--divider-color, #e0e0e0);
          stroke-width: 2; }
        .compass .rose { fill: var(--secondary-text-color); font-size: 11px;
          text-anchor: middle; dominant-baseline: middle; }
        .compass .needle { fill: var(--primary-color); stroke: var(--primary-color);
          stroke-width: 3; stroke-linecap: round; }
        .compass .hub { fill: var(--primary-color); }
        .hail-badge { display: flex; align-items: center; gap: 8px;
          font-size: 1.3rem; font-weight: 600; min-height: 96px; }
        .hail-dot { width: 12px; height: 12px; border-radius: 50%; }
        .warn { color: var(--error-color); padding: 8px 0; }
        .tip-bubble {
          position: absolute; left: 50%; transform: translateX(-50%);
          bottom: calc(100% + 8px); width: 210px; padding: 8px 10px;
          box-sizing: border-box; border-radius: 8px;
          background: var(--ha-card-background, var(--card-background-color, #fff));
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color, #e0e0e0);
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28);
          font-size: 0.72rem; font-weight: 400; line-height: 1.4;
          white-space: normal; text-align: left;
          opacity: 0; visibility: hidden; transition: opacity 0.15s ease;
          z-index: 9; pointer-events: none;
        }
        .tip:hover .tip-bubble, .tip:focus .tip-bubble,
        .tip:focus-visible .tip-bubble { opacity: 1; visibility: visible; }
      </style>`;
  }
}

// Guard against being loaded twice (e.g. both auto-registered by the
// integration and added as a manual dashboard resource) -- defining the same
// custom element a second time throws and would break the card.
if (!customElements.get("storm-risk-card")) {
  customElements.define("storm-risk-card", StormRiskCard);
  customElements.define("storm-dynamics-card", StormDynamicsCard);

  window.customCards = window.customCards || [];
  window.customCards.push(
    {
      type: "storm-risk-card",
      name: "Storm Risk Card",
      description:
        "Convective storm risk gauge with score breakdown and a 24h forecast sparkline.",
      preview: true,
      documentationURL: "https://github.com/JRyall/Ha-storm-risk",
    },
    {
      type: "storm-dynamics-card",
      name: "Storm Dynamics Card",
      description:
        "Companion card: approximate storm motion (steering) and hail favourability.",
      preview: true,
      documentationURL: "https://github.com/JRyall/Ha-storm-risk",
    }
  );

  console.info(
    "%c STORM-RISK-CARD %c loaded ",
    "background:#fb8c00;color:#fff",
    ""
  );
}
