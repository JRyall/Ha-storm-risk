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
    tip: "CIN — Convective Inhibition. The “lid” holding storms down. A weak lid lets them fire easily; a strong one can cap them, or let energy build for an explosive release. Only counts when there's CAPE for it to act on.",
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
    if (!config || !config.entity) {
      throw new Error("Please define 'entity' (your Storm Risk score sensor).");
    }
    this._config = {
      name: "Storm Risk",
      show_breakdown: true,
      show_forecast: true,
      ...config,
    };
    this._root = this._root || this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return { entity: "sensor.storm_risk_storm_risk" };
  }

  _render() {
    if (!this._hass || !this._config) return;
    const entityId = this._config.entity;
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
    const mode = MODES[attrs.mode];
    if (mode) parts.push(mode);
    if (attrs.shear !== undefined && attrs.shear !== null) {
      parts.push(`shear ${Number(attrs.shear).toFixed(0)} m/s`);
    }
    if (attrs.trigger !== undefined && attrs.trigger !== null) {
      parts.push(`trigger ${Number(attrs.trigger).toFixed(0)}%`);
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
      <div class="gauge">
        <svg viewBox="0 0 120 120">
          <circle class="track" cx="60" cy="60" r="${r}"
            stroke-dasharray="${track} ${circ}"
            transform="rotate(${rotate} 60 60)"></circle>
          <circle cx="60" cy="60" r="${r}" stroke="${color}"
            stroke-dasharray="${fill} ${circ}"
            transform="rotate(${rotate} 60 60)"></circle>
        </svg>
        <div class="value tip" style="color:${color}"
          tabindex="0" aria-label="Storm risk ingredients score, 0 to 100">
          <span class="value-inner"><span class="num">${
            unavailable ? "-" : risk
          }</span><span class="suffix">/100</span></span>
          <span class="tip-bubble below center" role="tooltip">
            A 0–100 <b>ingredients score</b> — how loaded the atmosphere is for
            storms, from instability (CAPE), the lid (CIN) and moisture. It's
            <b>not</b> a probability that a storm will happen.
          </span>
        </div>
      </div>`;
  }

  _breakdown(attrs) {
    const rows = INGREDIENTS.map((ing) => {
      const score = Number(attrs[ing.key] ?? 0);
      const pct = Math.max(0, Math.min(100, (score / SCORE_CAP) * 100));
      const raw = attrs[ing.raw];
      const sub =
        raw === undefined || raw === null
          ? ""
          : `${Number(raw).toFixed(ing.digits)} ${ing.unit}`;
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
    const h = 56;
    const pad = 4;
    const n = forecast.length;
    const pts = forecast.map((p, i) => {
      const x = pad + (i * (w - 2 * pad)) / (n - 1);
      const v = Math.max(0, Math.min(100, Number(p.storm_risk) || 0));
      const y = h - pad - (v / 100) * (h - 2 * pad);
      return [x, y];
    });
    const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const area =
      `${pad},${h - pad} ` + line + ` ${(w - pad).toFixed(1)},${h - pad}`;
    const first = forecast[0].datetime?.slice(11, 16) ?? "";
    const last = forecast[n - 1].datetime?.slice(11, 16) ?? "";

    // Find the peak hour so the (otherwise flat-looking) sparkline gets a
    // concrete "worst it gets" readout: a dot on the curve plus a time/score.
    let peak = 0;
    for (let i = 1; i < n; i++) {
      if ((Number(forecast[i].storm_risk) || 0) > (Number(forecast[peak].storm_risk) || 0)) {
        peak = i;
      }
    }
    const peakVal = Math.round(
      Math.max(0, Math.min(100, Number(forecast[peak].storm_risk) || 0))
    );
    const peakTime = forecast[peak].datetime?.slice(11, 16) ?? "";
    const [pxRaw, pyRaw] = pts[peak];
    // The svg is stretched to the container width but kept at exactly h px
    // tall (preserveAspectRatio="none"), so x maps by % of width and y maps
    // 1:1 to px -- letting us position an HTML marker over the right vertex.
    const peakLeft = (pxRaw / w) * 100;
    const labelLeft = Math.max(16, Math.min(84, peakLeft));
    // Sit the label above the dot, or below it when the peak hugs the top.
    const labelAbove = pyRaw > 18;
    const labelTop = labelAbove ? pyRaw - 18 : pyRaw + 7;

    return `
      <div class="forecast">
        <div class="forecast-title tip" tabindex="0"
          aria-label="Next ${n} hour storm-risk score forecast">
          Next ${n}h storm risk
          <span class="tip-bubble" role="tooltip">
            The storm-risk score (0–100) for each of the next ${n} hours. The
            dot marks the forecast <b>peak</b> — the time it's highest and the
            score it reaches.
          </span>
        </div>
        <div class="spark-wrap">
          <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
            <polygon class="spark-area" points="${area}"></polygon>
            <polyline class="spark-line" points="${line}"></polyline>
          </svg>
          <span class="peak-dot" style="left:${peakLeft.toFixed(1)}%; top:${pyRaw.toFixed(1)}px; background:${color}"></span>
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
        .forecast-title { font-size: 0.8rem; color: var(--secondary-text-color); margin-bottom: 2px; }
        .spark-wrap { position: relative; }
        .forecast svg { width: 100%; height: 56px; display: block; }
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
          fill: none; stroke: var(--primary-color); stroke-width: 2;
          vector-effect: non-scaling-stroke;
        }
        .spark-area { fill: var(--primary-color); opacity: 0.12; }
        .forecast-axis {
          display: flex; justify-content: space-between;
          font-size: 0.7rem; color: var(--secondary-text-color);
        }
        .warn { color: var(--error-color); padding: 8px 0; }
      </style>`;
  }
}

// Guard against being loaded twice (e.g. both auto-registered by the
// integration and added as a manual dashboard resource) -- defining the same
// custom element a second time throws and would break the card.
if (!customElements.get("storm-risk-card")) {
  customElements.define("storm-risk-card", StormRiskCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "storm-risk-card",
    name: "Storm Risk Card",
    description:
      "Convective storm risk gauge with score breakdown and a 24h forecast sparkline.",
    preview: true,
    documentationURL: "https://github.com/JRyall/Ha-storm-risk",
  });

  console.info(
    "%c STORM-RISK-CARD %c loaded ",
    "background:#fb8c00;color:#fff",
    ""
  );
}
