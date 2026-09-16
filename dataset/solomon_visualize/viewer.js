(() => {
  "use strict";

  const caseData = window.SOLOMON_CASE;
  const svg = document.querySelector("#customer-chart");
  const chartWrap = svg.parentElement;
  const summary = document.querySelector("#point-summary");
  const interactionHint = document.querySelector(".legend .hint");
  const customerButtons = [...document.querySelectorAll("[data-count]")];
  const riskButtons = [...document.querySelectorAll("[data-risk-count]")];
  const NS = "http://www.w3.org/2000/svg";
  let selectedCount = 25;
  let selectedRiskCount = 0;
  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 16;
  const view = { zoom: 1, panX: 0, panY: 0 };
  let geometry = null;

  const zoomControls = document.createElement("div");
  zoomControls.className = "zoom-controls";
  zoomControls.setAttribute("role", "group");
  zoomControls.setAttribute("aria-label", "Điều khiển thu phóng biểu đồ");
  zoomControls.innerHTML = `
    <button type="button" data-zoom="in" aria-label="Phóng to" title="Phóng to">+</button>
    <button type="button" data-zoom="out" aria-label="Thu nhỏ" title="Thu nhỏ">−</button>
    <button type="button" class="zoom-reset" data-zoom="reset" aria-label="Đặt lại vùng nhìn" title="Đặt lại vùng nhìn">Đặt lại</button>
    <output class="zoom-level" aria-live="polite">100%</output>
  `;
  chartWrap.append(zoomControls);
  if (interactionHint) interactionHint.textContent = "Cuộn để zoom · Kéo để di chuyển · Nhấp đúp để đặt lại";

  const makeSvg = (tag, attributes = {}, text = "") => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== "") node.textContent = text;
    return node;
  };

  const niceStep = (range, targetTicks = 8) => {
    const rough = range / targetTicks;
    const power = 10 ** Math.floor(Math.log10(rough || 1));
    const fraction = rough / power;
    const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
    return niceFraction * power;
  };

  const tickValues = (min, max, step) => {
    const first = Math.ceil(min / step) * step;
    const ticks = [];
    for (let value = first; value <= max + step * 0.001; value += step) {
      ticks.push(Number(value.toFixed(8)));
    }
    return ticks;
  };

  const resetView = () => {
    view.zoom = 1;
    view.panX = 0;
    view.panY = 0;
    render();
  };

  const setZoom = (nextZoom, anchor = null) => {
    if (!geometry) return;
    const oldZoom = view.zoom;
    const newZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom));
    if (newZoom === oldZoom) return;

    if (anchor) {
      const xRatio = (anchor.x - geometry.margin.left) / geometry.plotWidth;
      const yRatio = (anchor.y - geometry.margin.top) / geometry.plotHeight;
      const anchorX = geometry.xMin + xRatio * (geometry.xMax - geometry.xMin);
      const anchorY = geometry.yMax - yRatio * (geometry.yMax - geometry.yMin);
      const nextXSpan = geometry.baseXSpan / newZoom;
      const nextYSpan = geometry.baseYSpan / newZoom;
      const nextCenterX = anchorX - (xRatio - 0.5) * nextXSpan;
      const nextCenterY = anchorY + (yRatio - 0.5) * nextYSpan;
      view.panX = nextCenterX - geometry.baseXCenter;
      view.panY = nextCenterY - geometry.baseYCenter;
    }

    view.zoom = newZoom;
    render();
  };

  const render = () => {
    const width = Math.max(svg.clientWidth, 320);
    const height = Math.max(svg.clientHeight, 420);
    const margin = { top: 28, right: 30, bottom: 58, left: 68 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const visible = caseData.points.filter(point => point.id === 0 || point.id <= selectedCount);
    const visibleRisks = (caseData.risks || []).slice(0, selectedRiskCount);
    const xs = visible.map(point => point.x).concat(visibleRisks.flatMap(risk => [risk.x - risk.radius, risk.x + risk.radius]));
    const ys = visible.map(point => point.y).concat(visibleRisks.flatMap(risk => [risk.y - risk.radius, risk.y + risk.radius]));
    const xRange = Math.max(Math.max(...xs) - Math.min(...xs), 1);
    const yRange = Math.max(Math.max(...ys) - Math.min(...ys), 1);
    const xPad = Math.max(2, xRange * 0.07);
    const yPad = Math.max(2, yRange * 0.07);
    const paddedXMin = Math.min(...xs) - xPad;
    const paddedXMax = Math.max(...xs) + xPad;
    const paddedYMin = Math.min(...ys) - yPad;
    const paddedYMax = Math.max(...ys) + yPad;
    const xCenter = (paddedXMin + paddedXMax) / 2;
    const yCenter = (paddedYMin + paddedYMax) / 2;
    const unitsPerPixel = Math.max(
      (paddedXMax - paddedXMin) / plotWidth,
      (paddedYMax - paddedYMin) / plotHeight
    );
    const baseXSpan = unitsPerPixel * plotWidth;
    const baseYSpan = unitsPerPixel * plotHeight;
    const xSpan = baseXSpan / view.zoom;
    const ySpan = baseYSpan / view.zoom;
    const viewXCenter = xCenter + view.panX;
    const viewYCenter = yCenter + view.panY;
    const xMin = viewXCenter - xSpan / 2;
    const xMax = viewXCenter + xSpan / 2;
    const yMin = viewYCenter - ySpan / 2;
    const yMax = viewYCenter + ySpan / 2;
    const viewUnitsPerPixel = unitsPerPixel / view.zoom;
    const gridStep = niceStep(viewUnitsPerPixel * 80, 1);
    const toX = value => margin.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
    const toY = value => margin.top + plotHeight - ((value - yMin) / (yMax - yMin)) * plotHeight;
    const pointRadius = selectedCount === 25 ? 14 : 11;
    const fontSize = selectedCount === 25 ? 10 : 8;

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    geometry = {
      width, height, margin, plotWidth, plotHeight,
      xMin, xMax, yMin, yMax,
      baseXSpan, baseYSpan,
      baseXCenter: xCenter,
      baseYCenter: yCenter
    };
    zoomControls.querySelector(".zoom-level").value = `${Math.round(view.zoom * 100)}%`;
    zoomControls.querySelector('[data-zoom="in"]').disabled = view.zoom >= MAX_ZOOM;
    zoomControls.querySelector('[data-zoom="out"]').disabled = view.zoom <= MIN_ZOOM;

    const defs = makeSvg("defs");
    const clipPath = makeSvg("clipPath", { id: "plot-clip" });
    clipPath.append(makeSvg("rect", {
      x: margin.left,
      y: margin.top,
      width: plotWidth,
      height: plotHeight
    }));
    defs.append(clipPath);
    svg.append(defs);

    tickValues(xMin, xMax, gridStep).forEach(value => {
      const x = toX(value);
      svg.append(makeSvg("line", { x1: x, y1: margin.top, x2: x, y2: margin.top + plotHeight, class: "grid-line" }));
      svg.append(makeSvg("text", { x, y: height - 30, class: "tick-label", "text-anchor": "middle" }, value));
    });
    tickValues(yMin, yMax, gridStep).forEach(value => {
      const y = toY(value);
      svg.append(makeSvg("line", { x1: margin.left, y1: y, x2: margin.left + plotWidth, y2: y, class: "grid-line" }));
      svg.append(makeSvg("text", { x: margin.left - 12, y: y + 4, class: "tick-label", "text-anchor": "end" }, value));
    });

    svg.append(makeSvg("line", { x1: margin.left, y1: margin.top + plotHeight, x2: margin.left + plotWidth, y2: margin.top + plotHeight, class: "axis-line" }));
    svg.append(makeSvg("line", { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotHeight, class: "axis-line" }));
    svg.append(makeSvg("text", { x: margin.left + plotWidth / 2, y: height - 8, class: "axis-label", "text-anchor": "middle" }, "X coordinate"));
    svg.append(makeSvg("text", { x: 17, y: margin.top + plotHeight / 2, class: "axis-label", "text-anchor": "middle", transform: `rotate(-90 17 ${margin.top + plotHeight / 2})` }, "Y coordinate"));

    const plotLayer = makeSvg("g", { class: "plot-content", "clip-path": "url(#plot-clip)" });
    const riskLayer = makeSvg("g", { class: "risk-coverage-layer", "aria-hidden": "true" });
    visibleRisks.forEach(risk => {
      riskLayer.append(makeSvg("circle", {
        cx: toX(risk.x),
        cy: toY(risk.y),
        r: risk.radius / viewUnitsPerPixel,
        class: "risk-coverage"
      }));
    });
    plotLayer.append(riskLayer);

    visible.forEach(point => {
      const x = toX(point.x);
      const y = toY(point.y);
      const group = makeSvg("g", { class: `point${point.id === 0 ? " depot" : ""}`, tabindex: "0", role: "img", "aria-label": `${point.id === 0 ? "Depot" : `Customer ${point.id}`}: X ${point.x}, Y ${point.y}` });
      group.append(makeSvg("title", {}, `${point.id === 0 ? "Depot" : `Customer ${point.id}`} · X: ${point.x}, Y: ${point.y}`));
      if (point.id === 0) {
        const r = pointRadius + 2;
        group.append(makeSvg("polygon", { points: `${x},${y-r} ${x+r},${y} ${x},${y+r} ${x-r},${y}` }));
      } else {
        group.append(makeSvg("circle", { cx: x, cy: y, r: pointRadius }));
      }
      group.append(makeSvg("text", { x, y, "font-size": fontSize }, point.id));
      plotLayer.append(group);
    });

    visibleRisks.forEach(risk => {
      const x = toX(risk.x);
      const y = toY(risk.y);
      const size = selectedCount === 25 ? 17 : 14;
      const group = makeSvg("g", {
        class: "risk-point",
        tabindex: "0",
        role: "img",
        "aria-label": `Risk ${risk.id}: X ${risk.x}, Y ${risk.y}, bán kính ${risk.radius}`
      });
      group.append(makeSvg("title", {}, `Risk ${risk.id} · X: ${risk.x}, Y: ${risk.y} · Bán kính: ${risk.radius}`));
      group.append(makeSvg("polygon", { points: `${x},${y-size} ${x+size},${y+size*0.78} ${x-size},${y+size*0.78}` }));
      group.append(makeSvg("text", { x, y: y + size * 0.18, "font-size": selectedCount === 25 ? 10 : 8 }, risk.id));
      plotLayer.append(group);
    });

    svg.append(plotLayer);

    summary.textContent = `${Math.min(selectedCount, caseData.points.length - 1)} customer + depot · ${visibleRisks.length} risk`;
  };

  customerButtons.forEach(button => {
    button.addEventListener("click", () => {
      selectedCount = Number(button.dataset.count);
      customerButtons.forEach(item => item.setAttribute("aria-pressed", String(item === button)));
      resetView();
    });
  });

  riskButtons.forEach(button => {
    button.addEventListener("click", () => {
      selectedRiskCount = Number(button.dataset.riskCount);
      riskButtons.forEach(item => item.setAttribute("aria-pressed", String(item === button)));
      resetView();
    });
  });

  zoomControls.addEventListener("click", event => {
    const action = event.target.closest("button")?.dataset.zoom;
    if (action === "in") setZoom(view.zoom * 1.35);
    if (action === "out") setZoom(view.zoom / 1.35);
    if (action === "reset") resetView();
  });

  svg.addEventListener("wheel", event => {
    if (!geometry) return;
    const rect = svg.getBoundingClientRect();
    const anchor = {
      x: (event.clientX - rect.left) * geometry.width / rect.width,
      y: (event.clientY - rect.top) * geometry.height / rect.height
    };
    const insidePlot = anchor.x >= geometry.margin.left
      && anchor.x <= geometry.margin.left + geometry.plotWidth
      && anchor.y >= geometry.margin.top
      && anchor.y <= geometry.margin.top + geometry.plotHeight;
    if (!insidePlot) return;
    event.preventDefault();
    setZoom(view.zoom * (event.deltaY < 0 ? 1.2 : 1 / 1.2), anchor);
  }, { passive: false });

  let dragPoint = null;
  svg.addEventListener("pointerdown", event => {
    if (event.button !== 0 || !geometry) return;
    dragPoint = { x: event.clientX, y: event.clientY };
    svg.setPointerCapture(event.pointerId);
    svg.classList.add("is-panning");
  });

  svg.addEventListener("pointermove", event => {
    if (!dragPoint || !geometry) return;
    const rect = svg.getBoundingClientRect();
    const dx = (event.clientX - dragPoint.x) * geometry.width / rect.width;
    const dy = (event.clientY - dragPoint.y) * geometry.height / rect.height;
    view.panX -= dx * (geometry.xMax - geometry.xMin) / geometry.plotWidth;
    view.panY += dy * (geometry.yMax - geometry.yMin) / geometry.plotHeight;
    dragPoint = { x: event.clientX, y: event.clientY };
    render();
  });

  const stopPanning = event => {
    if (!dragPoint) return;
    dragPoint = null;
    svg.classList.remove("is-panning");
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
  };
  svg.addEventListener("pointerup", stopPanning);
  svg.addEventListener("pointercancel", stopPanning);
  svg.addEventListener("dblclick", resetView);

  new ResizeObserver(render).observe(svg.parentElement);
  render();
})();
