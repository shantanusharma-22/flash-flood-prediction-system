        // Global variables & state
        let map, mapTileLayer, wardLayers = {}, sensorMarkers = [], routeLines = [];
        let rainfallChart, fosChart;
        let activeWardsData = [];
        let sensorData = [];
        let historicalData = [];
        let currentMode = 'command';
        let currentTab = 'gis-map';
        let isSirenPlaying = false;
        let audioCtx = null, sirenOsc1 = null, sirenOsc2 = null;

        // Live evacuation countdown state (seconds)
        let leadTimeSeconds = 0;
        let lastLeadMinutes = null;

        // HTML-escape helper: every server- or user-supplied value that is placed
        // into innerHTML must pass through this first (XSS hardening).
        function esc(value) {
            return String(value ?? '').replace(/[&<>"']/g, (c) => (
                { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
            ));
        }

        function formatLeadTime(totalSeconds) {
            const s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
            const pad = (n) => String(n).padStart(2, '0');
            return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
        }

        function renderLeadTime() {
            const el = document.getElementById('lead-time-display');
            if (el) el.innerText = formatLeadTime(leadTimeSeconds);
        }

        function setLeadTime(minutes) {
            const mins = Math.max(0, Math.floor(Number(minutes) || 0));
            if (mins !== lastLeadMinutes) {
                lastLeadMinutes = mins;
                leadTimeSeconds = mins * 60;
            }
            renderLeadTime();
        }

        // Ticks the countdown once per second; re-syncs whenever telemetry reports
        // a new lead time.
        setInterval(() => {
            if (leadTimeSeconds > 0) {
                leadTimeSeconds -= 1;
                renderLeadTime();
            }
        }, 1000);

        // Tile layer URLs
        const TILE_LAYERS = {
            osm: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            topo: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        };

        document.addEventListener('DOMContentLoaded', () => {
            lucide.createIcons();
            startClocks();
            initMap();
            initCharts();
            initSlopeCanvas();
            fetchData();
            fetchSOSAlerts();

            // WebSocket telemetry stream with fallback polling
            initWebSocket();

            // Register PWA service worker
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW registration error:', err));
            }
        });

        // 1. Clock Updates
        function startClocks() {
            setInterval(() => {
                const now = new Date();
                const utc = now.toUTCString().split(' ')[4] + ' UTC';
                const ist = now.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST';
                const clockEl = document.getElementById('live-clocks');
                if (clockEl) clockEl.innerText = `${utc} | ${ist}`;
            }, 1000);
        }

        // 2. Mode Switcher (NDRF Command vs Citizen Mobile Portal)
        function switchAppMode(mode) {
            currentMode = mode;
            const commandEl = document.getElementById('app-mode-command');
            const citizenEl = document.getElementById('app-mode-citizen');
            const btnCommand = document.getElementById('mode-btn-command');
            const btnCitizen = document.getElementById('mode-btn-citizen');

            if (mode === 'command') {
                commandEl.classList.remove('hidden');
                citizenEl.classList.add('hidden');
                btnCommand.className = 'px-3 py-1 rounded-lg text-xs font-bold transition bg-red-600 text-white shadow-sm flex items-center gap-1.5';
                btnCitizen.className = 'px-3 py-1 rounded-lg text-xs font-medium transition text-slate-400 hover:text-white flex items-center gap-1.5';
                if (map) setTimeout(() => map.invalidateSize(), 200);
            } else {
                commandEl.classList.add('hidden');
                citizenEl.classList.remove('hidden');
                btnCitizen.className = 'px-3 py-1 rounded-lg text-xs font-bold transition bg-red-600 text-white shadow-sm flex items-center gap-1.5';
                btnCommand.className = 'px-3 py-1 rounded-lg text-xs font-medium transition text-slate-400 hover:text-white flex items-center gap-1.5';
                populateCitizenWards();
            }
            lucide.createIcons();
        }

        // 3. Ribbon Tab Switcher
        function switchTab(tabId) {
            currentTab = tabId;
            const tabs = ['gis-map', 'telemetry', 'slope-physics', 'gemini-ai', 'simulator', 'early-warnings', 'sos-radar', 'historical'];
            tabs.forEach(t => {
                const view = document.getElementById(`view-${t}`);
                const tab = document.getElementById(`tab-${t}`);
                if (view) view.classList.add('hidden');
                if (tab) tab.classList.remove('tab-active');
            });
            const activeView = document.getElementById(`view-${tabId}`);
            const activeTab = document.getElementById(`tab-${tabId}`);
            if (activeView) activeView.classList.remove('hidden');
            if (activeTab) activeTab.classList.add('tab-active');

            if (tabId === 'gis-map' && map) {
                setTimeout(() => map.invalidateSize(), 200);
            }
            if (tabId === 'slope-physics') {
                drawSlopeCanvas();
            }
            lucide.createIcons();
        }

        // 4. Map Initialization & Layers
        function initMap() {
            // Default center at Chamoli Basin
            map = L.map('map').setView([30.485, 79.698], 10);
            
            mapTileLayer = L.tileLayer(TILE_LAYERS.topo, {
                maxZoom: 18,
                attribution: '© OpenTopoMap | NDRF GIS Disaster Engine'
            }).addTo(map);
        }

        function changeMapLayer(layerKey) {
            if (map && mapTileLayer) {
                map.removeLayer(mapTileLayer);
                const url = TILE_LAYERS[layerKey] || TILE_LAYERS.topo;
                mapTileLayer = L.tileLayer(url, { maxZoom: 18 }).addTo(map);
            }
        }

        function jumpToLocation(lat, lng, zoom = 12) {
            if (map) {
                map.flyTo([lat, lng], zoom, { duration: 1.5 });
            }
        }

        // 5. Chart.js Graphs
        function initCharts() {
            const ctx1 = document.getElementById('chart-rainfall-moisture').getContext('2d');
            rainfallChart = new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: ['-30m', '-25m', '-20m', '-15m', '-10m', '-5m', 'NOW'],
                    datasets: [
                        {
                            label: 'Rainfall Intensity (mm/h)',
                            data: [15, 22, 45, 68, 85, 112, 118],
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.15)',
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2.5
                        },
                        {
                            label: 'Soil Moisture (% VWC)',
                            data: [20, 24, 28, 33, 38, 42, 43.8],
                            borderColor: '#fbbf24',
                            backgroundColor: 'rgba(251, 191, 36, 0.1)',
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2.5
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#cbd5e1', font: { family: 'Inter', size: 11 } } } },
                    scales: {
                        x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } },
                        y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });

            const ctx2 = document.getElementById('chart-fos-river').getContext('2d');
            fosChart = new Chart(ctx2, {
                type: 'line',
                data: {
                    labels: ['-30m', '-25m', '-20m', '-15m', '-10m', '-5m', 'NOW'],
                    datasets: [
                        {
                            label: 'Factor of Safety (FoS)',
                            data: [1.85, 1.62, 1.35, 1.15, 1.02, 0.96, 0.92],
                            borderColor: '#ef4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.15)',
                            fill: true,
                            tension: 0.35,
                            borderWidth: 2.5
                        },
                        {
                            label: 'River Surge vs Danger (m)',
                            data: [-3.2, -2.8, -1.5, 0.2, 1.8, 2.9, 3.5],
                            borderColor: '#60a5fa',
                            tension: 0.35,
                            borderWidth: 2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#cbd5e1', font: { family: 'Inter', size: 11 } } } },
                    scales: {
                        x: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } },
                        y: { grid: { color: 'rgba(51, 65, 85, 0.3)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });
        }

        // 6. Data Fetching
        async function fetchData() {
            try {
                const [wardsRes, sensorsRes, histRes] = await Promise.all([
                    fetch('/api/wards'),
                    fetch('/api/sensors'),
                    fetch('/api/historical-events')
                ]);

                activeWardsData = await wardsRes.json();
                sensorData = await sensorsRes.json();
                historicalData = await histRes.json();

                updateWardUI(activeWardsData);
                updateSensorTable(sensorData);
                updateHistoricalUI(historicalData);
                renderSensorMarkers(sensorData);
            } catch (err) {
                console.error("Telemetry fetch error:", err);
            }
        }

        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
            try {
                const ws = new WebSocket(wsUrl);
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.wards) {
                        activeWardsData = data.wards;
                        updateWardUI(activeWardsData);
                    }
                    if (data.sensors) {
                        sensorData = data.sensors;
                        updateSensorTable(sensorData);
                    }
                };
                ws.onerror = () => {
                    // Fallback to polling every 3 seconds
                    setInterval(fetchData, 3000);
                };
            } catch (e) {
                setInterval(fetchData, 3000);
            }
        }

        // 7. Ward Rendering on Map and Sidebar
        function updateWardUI(wards) {
            if (!wards || wards.length === 0) return;
            const wardListEl = document.getElementById('ward-list');
            wardListEl.innerHTML = '';

            let maxRiskWard = wards[0];

            // Clear old route lines
            routeLines.forEach(line => map.removeLayer(line));
            routeLines = [];

            wards.forEach(w => {
                if (w.risk_score > maxRiskWard.risk_score) maxRiskWard = w;

                const hexColor = w.risk_level === 'RED' ? '#ef4444' : (w.risk_level === 'ORANGE' ? '#f97316' : (w.risk_level === 'YELLOW' ? '#eab308' : '#10b981'));
                const badgeClass = w.risk_level === 'RED' ? 'bg-red-600 text-white' : (w.risk_level === 'ORANGE' ? 'bg-orange-500 text-white' : (w.risk_level === 'YELLOW' ? 'bg-yellow-500 text-black' : 'bg-emerald-600 text-white'));

                // Render Map Polygon
                if (wardLayers[w.ward_id]) {
                    map.removeLayer(wardLayers[w.ward_id]);
                }
                const polygon = L.polygon(w.polygon, {
                    color: hexColor,
                    fillColor: hexColor,
                    fillOpacity: 0.45,
                    weight: 2.5
                }).addTo(map);

                polygon.bindPopup(`
                    <div class="text-xs font-sans p-1">
                        <strong class="text-sm text-slate-900 font-bold">${esc(w.ward_name)}</strong><br/>
                        <div class="my-1">
                            <b>Alert Level:</b> <span class="px-2 py-0.5 rounded text-white font-bold" style="background:${hexColor}">${esc(w.risk_level)} (${esc(w.risk_score)}/100)</span>
                        </div>
                        <div><b>Factor of Safety (FoS):</b> <span class="font-mono font-bold">${esc(w.factor_of_safety)}</span></div>
                        <div><b>Rainfall Rate:</b> <span class="font-mono text-blue-600 font-bold">${esc(w.rainfall_1h_mm)} mm/h</span></div>
                        <div><b>Lead Time:</b> <span class="font-mono text-red-600 font-bold">${esc(w.estimated_lead_time_min)} mins</span></div>
                        <div class="mt-1 text-slate-600"><b>Primary Route:</b> ${esc(w.evacuation_routes && w.evacuation_routes.length > 0 ? w.evacuation_routes[0] : 'High-ground trail')}</div>
                    </div>
                `);
                wardLayers[w.ward_id] = polygon;

                // Draw evacuation dashed trail
                if (document.getElementById('chk-evac-routes').checked && w.polygon.length >= 2) {
                    const center = w.polygon[0];
                    const shelterOffset = [center[0] + 0.015, center[1] + 0.012];
                    const trail = L.polyline([center, shelterOffset], {
                        color: '#10b981',
                        weight: 3,
                        dashArray: '6, 8'
                    }).addTo(map);
                    trail.bindPopup(`<b>Safe Evacuation Trail:</b> ${esc(w.ward_name)} -> ${esc(w.shelter_locations && w.shelter_locations.length > 0 ? w.shelter_locations[0] : 'Relief Shelter')}`);
                    routeLines.push(trail);
                }

                // Render Ward Sidebar Card
                const card = document.createElement('div');
                card.className = `p-3 rounded-xl border border-slate-800 bg-slate-900/80 hover:border-slate-600 cursor-pointer space-y-1.5 transition`;
                card.onclick = () => {
                    map.fitBounds(polygon.getBounds());
                    polygon.openPopup();
                };
                card.innerHTML = `
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold text-white">${esc(w.ward_name)}</span>
                        <span class="px-2 py-0.5 text-[10px] font-bold rounded-full ${badgeClass}">${esc(w.risk_level)}</span>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-[11px] text-slate-400 font-mono">
                        <div>Rain: <span class="text-cyan-400 font-bold">${esc(w.rainfall_1h_mm)} mm/h</span></div>
                        <div>FoS: <span class="text-red-400 font-bold">${esc(w.factor_of_safety)}</span></div>
                    </div>
                    <div class="flex items-center justify-between text-[10px] text-slate-400 pt-0.5">
                        <span>Lead Time: <strong class="text-amber-400 font-mono font-bold">${esc(w.estimated_lead_time_min)} mins</strong></span>
                        <span class="text-slate-500">${esc(w.district)}</span>
                    </div>
                `;
                wardListEl.appendChild(card);
            });

            // Update Top Alert Marquee & Lead Time Display
            document.getElementById('highest-risk-ward').innerText = `${maxRiskWard.ward_name} (${maxRiskWard.risk_level})`;
            setLeadTime(maxRiskWard.estimated_lead_time_min);
            document.getElementById('lead-ward-name').innerText = maxRiskWard.ward_name;

            // Telemetry Hero Cards
            document.getElementById('sensor-val-rain').innerText = `${maxRiskWard.rainfall_1h_mm} mm/h`;
            document.getElementById('sensor-val-sm').innerText = `${maxRiskWard.soil_saturation_pct}% VWC`;
            document.getElementById('sensor-val-fos').innerHTML = `${maxRiskWard.factor_of_safety} <span class="text-xs text-red-500 uppercase font-bold">(${maxRiskWard.factor_of_safety < 1.0 ? 'CRITICAL' : 'STABLE'})</span>`;
            document.getElementById('sensor-val-river').innerText = `${maxRiskWard.river_water_level_m} m`;

            // Evacuation Hub Cards
            if (maxRiskWard.evacuation_routes && maxRiskWard.evacuation_routes.length > 0) {
                document.getElementById('route-primary').innerText = maxRiskWard.evacuation_routes[0];
            }
            if (maxRiskWard.shelter_locations && maxRiskWard.shelter_locations.length > 0) {
                document.getElementById('shelter-primary').innerText = maxRiskWard.shelter_locations[0];
            }
        }

        function renderSensorMarkers(sensors) {
            // Remove old markers
            sensorMarkers.forEach(m => map.removeLayer(m));
            sensorMarkers = [];

            sensors.forEach(s => {
                let iconColor = s.sensor_type === 'rain_gauge' ? '#06b6d4' : (s.sensor_type === 'soil_moisture' ? '#fbbf24' : '#60a5fa');
                const customIcon = L.divIcon({
                    className: 'custom-sensor-icon',
                    html: `
                        <div class="relative flex items-center justify-center">
                            <span class="absolute w-6 h-6 rounded-full opacity-75" style="background:${iconColor}; animation: radar-pulse 2s infinite;"></span>
                            <span class="w-3.5 h-3.5 rounded-full border-2 border-white shadow-lg" style="background:${iconColor}"></span>
                        </div>
                    `,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });

                const marker = L.marker([s.lat, s.lng], { icon: customIcon }).addTo(map);
                marker.bindPopup(`
                    <div class="text-xs font-sans p-1">
                        <strong class="text-slate-900">${esc(s.name)}</strong><br/>
                        <b>Type:</b> ${esc(s.sensor_type)}<br/>
                        <b>Reading:</b> <span class="font-mono font-bold text-cyan-600">${esc(s.value)} ${esc(s.unit)}</span><br/>
                        <b>Battery:</b> ${esc(s.battery_level)}% | <b>Signal:</b> ${esc(s.rssi_dbm || -65)} dBm<br/>
                        <span class="text-[10px] text-slate-500">${esc(s.timestamp)}</span>
                    </div>
                `);
                sensorMarkers.push(marker);
            });
        }

        function updateSensorTable(sensors) {
            const tbody = document.getElementById('sensor-table-body');
            if (!tbody) return;
            tbody.innerHTML = '';
            sensors.forEach(s => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="p-3 font-mono font-bold text-slate-400">${esc(s.sensor_id)}</td>
                    <td class="p-3 font-semibold text-white">${esc(s.name)}</td>
                    <td class="p-3 text-cyan-400 capitalize">${esc(String(s.sensor_type).replace('_', ' '))}</td>
                    <td class="p-3 font-mono font-bold text-amber-400">${esc(s.value)} ${esc(s.unit)}</td>
                    <td class="p-3 font-mono text-emerald-400">${esc(s.battery_level)}%</td>
                    <td class="p-3 font-mono text-slate-400">${esc(s.rssi_dbm || -65)} dBm</td>
                    <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">ONLINE</span></td>
                `;
                tbody.appendChild(tr);
            });
        }

        function updateHistoricalUI(events) {
            const tbody = document.getElementById('historical-table-body');
            if (!tbody) return;
            tbody.innerHTML = '';
            events.forEach(e => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="p-3 font-mono font-bold text-slate-400">${esc(e.id)}</td>
                    <td class="p-3 font-semibold text-white">${esc(e.location_name)}, ${esc(e.district)} (${esc(e.state)})</td>
                    <td class="p-3 text-cyan-400 font-medium">${esc(e.event_type)}</td>
                    <td class="p-3 text-slate-400">${esc(e.date)}</td>
                    <td class="p-3 font-mono text-amber-400">${esc(e.trigger_rainfall_mm)} mm</td>
                    <td class="p-3 font-mono text-red-400 font-bold">${esc(e.casualties)}</td>
                    <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${e.severity === 'Critical' ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-amber-950 text-amber-400 border border-amber-800'}">${esc(e.severity)}</span></td>
                    <td class="p-3 text-slate-300 text-[11px] max-w-xs">${esc(e.description)}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function filterWardList() {
            const query = document.getElementById('ward-search-input').value.toLowerCase();
            const filtered = activeWardsData.filter(w => w.ward_name.toLowerCase().includes(query) || w.district.toLowerCase().includes(query));
            updateWardUI(filtered);
        }

        function filterHistoricalTable() {
            const query = document.getElementById('hist-search-input').value.toLowerCase();
            const filtered = historicalData.filter(e => e.location_name.toLowerCase().includes(query) || e.district.toLowerCase().includes(query) || e.event_type.toLowerCase().includes(query));
            updateHistoricalUI(filtered);
        }

        function toggleEvacuationRoutes() {
            updateWardUI(activeWardsData);
        }

        // 8. Geotechnical Slope Canvas Drawing
        function initSlopeCanvas() {
            drawSlopeCanvas();
        }

        function drawSlopeCanvas() {
            const canvas = document.getElementById('slopeCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const w = canvas.width;
            const h = canvas.height;

            const slopeDeg = parseFloat(document.getElementById('input-slope')?.value || 47.5);
            const vwc = parseFloat(document.getElementById('input-vwc')?.value || 0.42);

            ctx.clearRect(0, 0, w, h);

            // Slope geometry
            const rad = (slopeDeg * Math.PI) / 180;
            const startX = 60;
            const startY = 60;
            const endX = w - 60;
            const endY = Math.min(h - 40, startY + (endX - startX) * Math.tan(rad * 0.45));

            // Bedrock (Bottom polygon)
            ctx.fillStyle = '#0f172a';
            ctx.beginPath();
            ctx.moveTo(startX, startY + 40);
            ctx.lineTo(endX, endY + 40);
            ctx.lineTo(endX, h);
            ctx.lineTo(startX, h);
            ctx.closePath();
            ctx.fill();

            // Soil Layer
            const grad = ctx.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0, '#78350f');
            grad.addColorStop(1, '#451a03');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
            ctx.lineTo(endX, endY + 40);
            ctx.lineTo(startX, startY + 40);
            ctx.closePath();
            ctx.fill();

            // Water table saturation line
            const satRatio = vwc / 0.45;
            const waterYOffset = 40 * (1 - satRatio);
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 2.5;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(startX, startY + waterYOffset);
            ctx.lineTo(endX, endY + waterYOffset);
            ctx.stroke();
            ctx.setLineDash([]);

            // Critical Failure Shear Plane (Red dashed)
            ctx.strokeStyle = '#ef4444';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(startX + 20, startY + 38);
            ctx.lineTo(endX - 20, endY + 38);
            ctx.stroke();

            // Force vectors (Driving vs Resisting)
            // Midpoint of slope
            const midX = (startX + endX) / 2;
            const midY = (startY + endY) / 2;

            // Driving force arrow (Down slope)
            ctx.strokeStyle = '#f87171';
            ctx.fillStyle = '#f87171';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(midX, midY);
            ctx.lineTo(midX + 50 * Math.cos(rad * 0.45), midY + 50 * Math.sin(rad * 0.45));
            ctx.stroke();

            // Resisting strength arrow (Up slope)
            ctx.strokeStyle = '#34d399';
            ctx.fillStyle = '#34d399';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.moveTo(midX, midY);
            ctx.lineTo(midX - 45 * Math.cos(rad * 0.45), midY - 45 * Math.sin(rad * 0.45));
            ctx.stroke();

            // Labels
            ctx.fillStyle = '#f1f5f9';
            ctx.font = '11px JetBrains Mono';
            ctx.fillText(`Slope: ${slopeDeg}°`, startX, startY - 10);
            ctx.fillStyle = '#38bdf8';
            ctx.fillText(`Water Saturation: ${Math.round(satRatio * 100)}%`, startX + 10, startY + waterYOffset - 8);
            ctx.fillStyle = '#ef4444';
            ctx.fillText(`Critical Shear Slip Plane`, endX - 160, endY + 55);
        }

        function updatePhysicsModel() {
            const slope = parseFloat(document.getElementById('input-slope').value);
            const vwc = parseFloat(document.getElementById('input-vwc').value);
            const cohesion = parseFloat(document.getElementById('input-cohesion').value);
            const friction = parseFloat(document.getElementById('input-friction').value);
            const depth = parseFloat(document.getElementById('input-depth').value);
            const root = parseFloat(document.getElementById('input-root').value);

            document.getElementById('val-slope').innerText = `${slope}°`;
            document.getElementById('val-vwc').innerText = `${vwc} (${Math.round((vwc/0.45)*100)}% Sat)`;
            document.getElementById('val-cohesion').innerText = `${cohesion} kPa`;
            document.getElementById('val-friction').innerText = `${friction}°`;
            document.getElementById('val-depth').innerText = `${depth} m`;
            document.getElementById('val-root').innerText = `${root} kPa`;

            drawSlopeCanvas();

            // Physics FoS formula
            const theta = slope * (Math.PI / 180);
            const phi = friction * (Math.PI / 180);
            const m = Math.min(vwc / 0.45, 1.0);
            const gamma_sat = 16.0 + (m * 0.45 * 9.81);
            const eff_norm = Math.max(0, (gamma_sat - (m * 9.81)) * depth * (Math.cos(theta) ** 2));
            const resisting = (cohesion + root) + (eff_norm * Math.tan(phi));
            const driving = gamma_sat * depth * Math.sin(theta) * Math.cos(theta);
            const fos = Math.max(0.1, (resisting / Math.max(0.001, driving))).toFixed(2);

            document.getElementById('calc-fos').innerText = fos;
            document.getElementById('calc-driving').innerText = `${driving.toFixed(1)} kPa`;
            document.getElementById('calc-resisting').innerText = `${resisting.toFixed(1)} kPa`;

            const statusEl = document.getElementById('calc-status');
            if (fos < 1.0) {
                statusEl.innerText = "IMMINENT SLOPE FAILURE";
                statusEl.className = "text-[10px] font-bold text-red-500";
            } else if (fos < 1.3) {
                statusEl.innerText = "HIGH RISK WARNING";
                statusEl.className = "text-[10px] font-bold text-amber-500";
            } else {
                statusEl.innerText = "STABLE SLOPE";
                statusEl.className = "text-[10px] font-bold text-emerald-500";
            }
        }

        // 9. Simulation Triggers
        async function triggerScenario(scenario) {
            try {
                const res = await fetch('/api/simulator/scenario', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ scenario: scenario, ward_id: 'W-UK-CHM-04' })
                });
                const data = await res.json();
                fetchData();
                const log = document.getElementById('sms-log');
                if (log) {
                    const now = new Date().toLocaleTimeString();
                    log.innerHTML += `<div>[${now}] DRILL SCENARIO ACTIVATED: ${esc(scenario)} in Raini Sector.</div>`;
                    log.scrollTop = log.scrollHeight;
                }
            } catch (err) {
                console.error("Scenario trigger error:", err);
            }
        }

        function injectCustomRain() {
            const rain = parseFloat(document.getElementById('custom-rain-slider').value);
            fetch('/api/simulator/scenario', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scenario: 'CLOUDBURST', ward_id: 'W-UK-CHM-04', custom_rainfall: rain })
            }).then(() => fetchData());
        }

        // 10. Gemini AI Advisory Generator & Interactive Chat
        async function generateAIAdvisory() {
            const lang = document.getElementById('ai-language-select').value;
            try {
                const res = await fetch('/api/ai-advisory', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ward_id: 'W-UK-CHM-04', language: lang })
                });
                const data = await res.json();
                if (!res.ok) {
                    document.getElementById('ai-summary').innerText = 'AI advisory service unavailable — displaying last known telemetry only.';
                    return;
                }

                document.getElementById('ai-summary').innerText = data.situation_summary;

                const ulInst = document.getElementById('ai-instructions');
                ulInst.innerHTML = '';
                data.tactical_ndrf_instructions.forEach(ins => {
                    const li = document.createElement('li');
                    li.innerText = ins;
                    ulInst.appendChild(li);
                });

                const ulRes = document.getElementById('ai-resources');
                ulRes.innerHTML = '';
                data.resource_allocation_plan.forEach(r => {
                    const li = document.createElement('li');
                    li.innerText = r;
                    ulRes.appendChild(li);
                });

                document.getElementById('ai-broadcast').innerText = data.public_evacuation_broadcast;
            } catch (err) {
                console.error("AI advisory generation error:", err);
            }
        }

        function speakAIBroadcast() {
            const text = document.getElementById('ai-broadcast').innerText;
            if ('speechSynthesis' in window && text) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 0.95;
                utterance.pitch = 1.0;
                window.speechSynthesis.speak(utterance);
            }
        }

        async function handleChatSubmit(e) {
            e.preventDefault();
            const input = document.getElementById('chat-input');
            const msg = input.value.trim();
            if (!msg) return;
            input.value = '';

            const chatWindow = document.getElementById('chat-messages');
            chatWindow.innerHTML += `
                <div class="bg-slate-900 border border-slate-700 p-2.5 rounded-lg text-slate-200 text-right">
                    <strong>Commander:</strong> ${esc(msg)}
                </div>
            `;
            chatWindow.scrollTop = chatWindow.scrollHeight;

            try {
                const res = await fetch('/api/ai-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg, ward_id: 'W-UK-CHM-04' })
                });
                const data = await res.json();
                const reply = res.ok && data.reply
                    ? esc(data.reply)
                    : '<em>Copilot unavailable right now. Use the Lead-Time &amp; Dispatch tab for authoritative guidance.</em>';
                chatWindow.innerHTML += `
                    <div class="bg-indigo-950/70 border border-indigo-800/70 p-2.5 rounded-lg text-slate-200">
                        <strong>Gemini Copilot:</strong> ${reply}
                    </div>
                `;
                chatWindow.scrollTop = chatWindow.scrollHeight;
            } catch (err) {
                console.error("Chat error:", err);
            }
        }

        function sendQuickChat(prompt) {
            document.getElementById('chat-input').value = prompt;
            handleChatSubmit({ preventDefault: () => {} });
        }

        // 11. Lead Time SMS Dispatch & IAP Download
        async function dispatchAlertSMS() {
            try {
                const res = await fetch('/api/alerts/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ward_id: 'W-UK-CHM-04',
                        channels: ['SMS', 'VHF_RADIO', 'PUBLIC_SIREN'],
                        severity: 'RED'
                    })
                });
                const data = await res.json();
                const log = document.getElementById('sms-log');
                const now = new Date().toLocaleTimeString();
                log.innerHTML += `<div class="text-amber-400">[${now}] EMERGENCY SMS BROADCAST TO ${esc(data.recipients_count)} CITIZENS IN ${esc(data.ward_name)}.</div>`;
                log.innerHTML += `<div class="text-red-400">[${now}] VHF CHANNEL 14 SIRENS ACTIVATED.</div>`;
                log.scrollTop = log.scrollHeight;
            } catch (e) {
                console.error("Dispatch error:", e);
            }
        }

        async function downloadIAPReport() {
            try {
                const res = await fetch('/api/reports/iap?ward_id=W-UK-CHM-04');
                const text = await res.text();
                const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `NDRF_Incident_Action_Plan_Raini_${new Date().toISOString().slice(0, 10)}.txt`;
                a.click();
            } catch (e) {
                console.error("IAP download error:", e);
            }
        }

        // 12. Citizen SOS Handling
        async function fetchSOSAlerts() {
            try {
                const res = await fetch('/api/citizen/sos');
                const sosList = await res.json();
                const tbody = document.getElementById('sos-table-body');
                if (!tbody) return;
                tbody.innerHTML = '';

                document.getElementById('sos-badge-count').innerText = sosList.filter(s => s.status !== 'RESOLVED').length;

                sosList.forEach(s => {
                    const tr = document.createElement('tr');
                    const nextStatus = s.status === 'PENDING' ? 'DISPATCHED' : 'RESOLVED';
                    tr.innerHTML = `
                        <td class="p-3 font-mono font-bold text-red-400">${esc(s.sos_id)}</td>
                        <td class="p-3 font-semibold text-white">${esc(s.citizen_name)}<br/><span class="text-slate-400 font-mono text-[10px]">${esc(s.phone_number)}</span></td>
                        <td class="p-3 text-slate-300">${esc(s.ward_name)}</td>
                        <td class="p-3 font-mono font-bold text-amber-400">${esc(s.people_count)}</td>
                        <td class="p-3 text-slate-300 max-w-xs">${esc(s.situation_desc)} ${s.requires_medical ? '<span class="text-[9px] bg-red-950 text-red-400 px-1.5 py-0.5 rounded font-bold ml-1">MEDICAL</span>' : ''}</td>
                        <td class="p-3 text-slate-400">${esc(s.timestamp)}</td>
                        <td class="p-3">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${s.status === 'PENDING' ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'}">${esc(s.status)}</span>
                            <button class="ml-2 px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] rounded">
                                ${s.status === 'PENDING' ? 'Dispatch Team' : 'Resolve'}
                            </button>
                        </td>
                    `;
                    // Bound via listener (not an inline onclick) so no attacker-
                    // controlled value is ever evaluated as script.
                    const triageBtn = tr.querySelector('button');
                    if (triageBtn) triageBtn.addEventListener('click', () => updateSOSTriage(s.sos_id, nextStatus));
                    tbody.appendChild(tr);
                });
            } catch (e) {
                console.error("SOS fetch error:", e);
            }
        }

        async function updateSOSTriage(sosId, newStatus) {
            await fetch(`/api/citizen/sos/${sosId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            fetchSOSAlerts();
        }

        async function handleCitizenSOSSubmit(e) {
            e.preventDefault();
            const name = document.getElementById('sos-name').value;
            const phone = document.getElementById('sos-phone').value;
            const people = parseInt(document.getElementById('sos-people').value) || 1;
            const desc = document.getElementById('sos-desc').value;
            const medical = document.getElementById('sos-medical').checked;
            const wid = document.getElementById('citizen-ward-select')?.value || 'W-UK-CHM-04';

            try {
                const res = await fetch('/api/citizen/sos', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ward_id: wid,
                        citizen_name: name,
                        phone_number: phone,
                        lat: 30.4820,
                        lng: 79.6950,
                        people_count: people,
                        situation_desc: desc,
                        requires_medical: medical
                    })
                });
                const data = await res.json();
                if (!res.ok) {
                    alert("⚠️ SOS BEACON REJECTED: Please check the name, phone number and situation details, then retry.");
                    return;
                }
                alert(`🚨 SOS BEACON TRANSMITTED (Ref: ${data.sos_id})!\nNDRF Rapid Action Battalion has been dispatched to your GPS location.`);
                fetchSOSAlerts();
            } catch (e) {
                console.error("SOS transmit error:", e);
                alert("⚠️ SOS TRANSMISSION FAILED: Network error. Please retry or call 1078.");
            }
        }

        // 13. Citizen Ward Lookup
        function populateCitizenWards() {
            const select = document.getElementById('citizen-ward-select');
            if (!select) return;
            select.innerHTML = '';
            activeWardsData.forEach(w => {
                const opt = document.createElement('option');
                opt.value = w.ward_id;
                opt.innerText = `${w.ward_name} (${w.district}, ${w.state})`;
                select.appendChild(opt);
            });
            if (activeWardsData.length > 0) {
                updateCitizenWardView(activeWardsData[0].ward_id);
            }
        }

        function updateCitizenWardView(wardId) {
            const w = activeWardsData.find(ward => ward.ward_id === wardId);
            if (!w) return;

            const badge = document.getElementById('citizen-risk-badge');
            badge.innerText = `${w.risk_level} ALERT (${w.risk_level === 'RED' ? 'CRITICAL' : 'MONITOR'})`;
            badge.className = `text-lg font-black font-heading ${w.risk_level === 'RED' ? 'text-red-400' : (w.risk_level === 'ORANGE' ? 'text-orange-400' : 'text-emerald-400')}`;

            document.getElementById('citizen-lead-time').innerText = `${w.estimated_lead_time_min} MINS`;
            document.getElementById('citizen-route-name').innerText = w.evacuation_routes && w.evacuation_routes.length > 0 ? w.evacuation_routes[0] : 'High-Ground Safe Trail';
            document.getElementById('citizen-shelter-name').innerText = w.shelter_locations && w.shelter_locations.length > 0 ? w.shelter_locations[0] : 'Community Shelter';
        }

        function detectCitizenLocation() {
            if ('geolocation' in navigator) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        alert(`GPS Location Acquired: Latitude ${pos.coords.latitude.toFixed(4)}, Longitude ${pos.coords.longitude.toFixed(4)}.\nNearest Hilly Ward matched: Raini Village (Ward 4).`);
                    },
                    (err) => {
                        alert("Geolocation permission not granted. Defaulting to Raini Sector.");
                    }
                );
            }
        }

        // 14. Emergency Siren Audio Engine (Web Audio API)
        function toggleEmergencySiren() {
            if (isSirenPlaying) {
                stopSiren();
            } else {
                startSiren();
            }
        }

        function startSiren() {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(440, audioCtx.currentTime);

                // Hi-Lo modulation
                const lfo = audioCtx.createOscillator();
                lfo.frequency.value = 1.2; // 1.2 Hz wobble
                const lfoGain = audioCtx.createGain();
                lfoGain.gain.value = 350; // Frequency swing

                lfo.connect(osc.frequency);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                gain.gain.setValueAtTime(0.12, audioCtx.currentTime);

                osc.start();
                lfo.start();

                sirenOsc1 = osc;
                sirenOsc2 = lfo;
                isSirenPlaying = true;

                document.getElementById('btn-siren').className = 'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition bg-red-600 text-white animate-pulse border border-red-500';
                document.getElementById('siren-status-text').innerText = 'SIREN ACTIVE';
            } catch (e) {
                console.error("Audio error:", e);
            }
        }

        function stopSiren() {
            if (sirenOsc1) sirenOsc1.stop();
            if (sirenOsc2) sirenOsc2.stop();
            if (audioCtx) audioCtx.close();
            isSirenPlaying = false;
            document.getElementById('btn-siren').className = 'px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700';
            document.getElementById('siren-status-text').innerText = 'Test Siren';
        }
    