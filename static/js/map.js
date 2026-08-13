document.addEventListener("DOMContentLoaded", function () {
  if (!document.getElementById("map")) return;

  const map = L.map("map", { zoomControl: true, scrollWheelZoom: false }).setView(
    [3.4516, -76.532],
    13
  );

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  function getColor(pct) {
    if (pct > 80) return "#e53e3e";
    if (pct > 50) return "#ed8936";
    return "#38a169";
  }

  function getLabel(pct) {
    if (pct > 80) return "Alta";
    if (pct > 50) return "Media";
    return "Baja";
  }

  fetch("/api/shelters")
    .then((r) => r.json())
    .then((shelters) => {
      shelters.forEach((s, idx) => {
        const pct =
          s.capacity > 0
            ? Math.round((s.current_occupancy / s.capacity) * 100)
            : 0;
        const color = getColor(pct);

        const marker = L.circleMarker([s.lat, s.lng], {
          radius: 16,
          fillColor: color,
          color: "#fff",
          weight: 3,
          opacity: 1,
          fillOpacity: 0.88,
        }).addTo(map);

        const aidHtml = s.aid_today
          ? `<div class="mt-2 pt-2" style="border-top:1px solid #e2e8f0">
               <small><b>🎯 Hoy:</b> ${s.aid_today}</small>
             </div>`
          : "";

        const popupHtml = `
          <div class="shelter-popup">
            <h5>${s.name}</h5>
            <small style="color:#64748b">${s.neighborhood || s.address}</small>
            <div class="mt-2">
              <span style="
                display:inline-block;
                padding:2px 8px;
                border-radius:99px;
                font-size:11px;
                font-weight:600;
                background:rgba(14,165,233,0.12);
                color:#0369a1;
              ">${s.population_type}</span>
            </div>
            <div class="mt-2">
              <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <small><b>Ocupación</b></small>
                <small style="color:${color};font-weight:700">${pct}% · ${getLabel(pct)}</small>
              </div>
              <div style="background:#e2e8f0;border-radius:99px;height:8px;overflow:hidden">
                <div style="width:${pct}%;height:100%;background:${color};border-radius:99px;transition:width 0.6s ease"></div>
              </div>
              <small style="color:#94a3b8">${s.current_occupancy} / ${s.capacity} personas</small>
            </div>
            ${aidHtml}
          </div>
        `;

        marker.bindPopup(popupHtml, { maxWidth: 240 });

        // Staggered appear animation via opacity
        marker.on("add", function () {
          const el = marker.getElement();
          if (el) {
            el.style.opacity = "0";
            setTimeout(() => {
              el.style.transition = "opacity 0.4s ease";
              el.style.opacity = "1";
            }, idx * 80);
          }
        });
      });
    })
    .catch((err) => console.error("Error cargando albergues:", err));
});
