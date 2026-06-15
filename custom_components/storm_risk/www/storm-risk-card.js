/**
 * Storm Risk Card
 *
 * A self-contained Lovelace card for the Storm Risk integration. It needs only
 * the Storm Risk (%) sensor: the score breakdown (cape_score / cin_score /
 * dp_score), the interpretation level, and the 24h forecast all live in that
 * one entity's attributes.
 *
 * Vanilla custom element — no build step, no external dependencies.
 */

const LEVELS = {
  none: { label: "Nothing brewing", color: "#43a047" },
  present: { label: "Ingredients present", color: "#fdd835" },
  meaningful: { label: "Meaningful potential", color: "#fb8c00" },
  loaded: { label: "Properly loaded setup", color: "#e53935" },
};

const INGREDIENTS = [
  { key: "cape_score", label: "CAPE", title: "Instability / fuel" },
  { key: "cin_score", label: "CIN", title: "Lid (gated by CAPE)" },
  { key: "dp_score", label: "Dew pt", title: "Low-level moisture" },
];

// Each ingredient contributes up to 33 points.
const SCORE_CAP = 33;

class StormRiskCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Please define 'entity' (your Storm Risk % sensor).");
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
            ? this._forecast(attrs.forecast || [])
            : ""
        }
      </ha-card>`;
  }

  _gauge(risk, color, unavailable) {
    // 220° sweep ring gauge. Circumference of the radius-52 circle is ~326.7.
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
        <div class="value" style="color:${color}">
          <span class="num">${unavailable ? "–" : risk}</span><span class="pct">%</span>
        </div>
      </div>`;
  }

  _breakdown(attrs) {
    const rows = INGREDIENTS.map((ing) => {
      const score = Number(attrs[ing.key] ?? 0);
      const pct = Math.max(0, Math.min(100, (score / SCORE_CAP) * 100));
      return `
        <div class="bar-row" title="${ing.title}">
          <span class="bar-label">${ing.label}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
          <span class="bar-val">${score.toFixed(0)}</span>
        </div>`;
    }).join("");
    return `<div class="breakdown">${rows}</div>`;
  }

  _forecast(forecast) {
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
    return `
      <div class="forecast">
        <div class="forecast-title">Next ${n}h storm risk</div>
        <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
          <polygon class="spark-area" points="${area}"></polygon>
          <polyline class="spark-line" points="${line}"></polyline>
        </svg>
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
        .value .num { font-size: 2.2rem; font-weight: 600; line-height: 1; }
        .value .pct { font-size: 1rem; margin-left: 2px; align-self: flex-start; margin-top: 6px; }
        .breakdown { flex: 1 1 auto; display: flex; flex-direction: column; gap: 8px; }
        .bar-row { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }
        .bar-label { width: 48px; color: var(--secondary-text-color); }
        .bar-track {
          flex: 1; height: 8px; border-radius: 4px;
          background: var(--divider-color, #e0e0e0); overflow: hidden;
        }
        .bar-fill {
          display: block; height: 100%; border-radius: 4px;
          background: var(--primary-color); transition: width 0.6s ease;
        }
        .bar-val { width: 24px; text-align: right; color: var(--primary-text-color); }
        .forecast { margin-top: 14px; }
        .forecast-title { font-size: 0.8rem; color: var(--secondary-text-color); margin-bottom: 2px; }
        .forecast svg { width: 100%; height: 56px; display: block; }
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

customElements.define("storm-risk-card", StormRiskCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "storm-risk-card",
  name: "Storm Risk Card",
  description:
    "Convective storm risk gauge with score breakdown and a 24h forecast sparkline.",
  preview: true,
  documentationURL: "https://github.com/jryall/ha-storm-risk",
});

console.info("%c STORM-RISK-CARD %c loaded ", "background:#fb8c00;color:#fff", "");
