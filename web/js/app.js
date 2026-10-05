/**
 * web/js/app.js
 * Main frontend coordinator.
 * Connects slider, WebSocket streaming, Chart.js updates, and UI controls.
 */

import { fetchRegistry, fetchMetrics, WSClient } from "./api.js";
import { renderCapabilityCurve } from "./chart.js";

let registryData = null;
let metricsData = null;
let wsClient = null;
let currentBlendId = "sweep_050";

const slider = document.getElementById("blendSlider");
const blendBadge = document.getElementById("currentBlendLabel");
const promptInput = document.getElementById("promptInput");
const generateBtn = document.getElementById("generateBtn");
const outputBox = document.getElementById("outputBox");

const SWEEP_MAP = {
  "0": "sweep_000",
  "0.25": "sweep_025",
  "0.5": "sweep_050",
  "0.75": "sweep_075",
  "1": "sweep_100",
};

async function init() {
  try {
    [registryData, metricsData] = await Promise.all([fetchRegistry(), fetchMetrics()]);
    
    // Initial chart render
    renderCapabilityCurve(metricsData, registryData, currentBlendId);
    updateBlendDisplay(currentBlendId);

    // Connect WebSocket
    setupWebSocket();

  } catch (err) {
    console.error("Initialization error:", err);
  }
}

function updateBlendDisplay(blendId) {
  currentBlendId = blendId;
  const blendInfo = registryData?.blends?.find((b) => b.id === blendId);
  if (blendInfo && blendBadge) {
    blendBadge.textContent = `${blendInfo.id} (${blendInfo.label})`;
  }
  
  // Re-render chart highlight
  renderCapabilityCurve(metricsData, registryData, currentBlendId);

  // Update pills UI active state
  document.querySelectorAll(".pill").forEach((pill) => {
    if (pill.dataset.id === blendId) {
      pill.classList.add("active");
    } else {
      pill.classList.remove("active");
    }
  });
}

// Slider change handler
if (slider) {
  slider.addEventListener("input", (e) => {
    const val = e.target.value;
    const blendId = SWEEP_MAP[val] || "sweep_050";
    updateBlendDisplay(blendId);
  });
}

// Variant pills click handler
document.querySelectorAll(".pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    const blendId = pill.dataset.id;
    if (blendId) {
      updateBlendDisplay(blendId);
      // Sync slider if sweep
      const sweepVal = Object.keys(SWEEP_MAP).find((k) => SWEEP_MAP[k] === blendId);
      if (sweepVal && slider) {
        slider.value = sweepVal;
      }
    }
  });
});

function setupWebSocket() {
  wsClient = new WSClient(
    (msg) => handleWSMessage(msg),
    (err) => console.error("WS Error:", err),
    () => console.log("WS Closed")
  );
  wsClient.connect();
}

function handleWSMessage(msg) {
  if (msg.type === "token") {
    outputBox.textContent += msg.text;
    outputBox.scrollTop = outputBox.scrollHeight;
  } else if (msg.type === "done") {
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate Tokens";
  } else if (msg.type === "error") {
    outputBox.textContent += `\n[Error: ${msg.message}]`;
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate Tokens";
  }
}

if (generateBtn) {
  generateBtn.addEventListener("click", () => {
    const text = promptInput.value.trim();
    if (!text) return;

    outputBox.textContent = "";
    generateBtn.disabled = true;
    generateBtn.textContent = "Streaming...";

    wsClient.send({
      type: "generate",
      blend_id: currentBlendId,
      prompt: text,
      max_tokens: 256,
      temperature: 0.7,
    });
  });
}

window.addEventListener("DOMContentLoaded", init);
