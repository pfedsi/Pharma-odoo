/** @odoo-module **/

import { Component, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// ── Template défini avec xml`...` (pas de fichier XML externe nécessaire) ─────

const MAP_TEMPLATE = xml`
<div class="o_map_picker_widget">

    <!-- Recherche d'adresse -->
    <div class="input-group mb-3">
        <span class="input-group-text bg-primary text-white border-primary">
            <i class="fa fa-search"/>
        </span>
        <input type="text"
               class="form-control"
               placeholder="Rechercher une adresse (ex : Avenue Habib Bourguiba, Tunis)…"
               t-model="state.query"
               t-on-keydown="onKeydown"/>
        <button class="btn btn-primary"
                t-on-click="onSearch"
                t-att-disabled="state.searching">
            <i t-if="state.searching" class="fa fa-spinner fa-spin me-1"/>
            <t t-esc="state.searching ? 'Recherche…' : 'Rechercher'"/>
        </button>
    </div>

    <!-- Erreur -->
    <div t-if="state.error"
         class="alert alert-warning d-flex align-items-center gap-2 py-2 mb-3">
        <i class="fa fa-exclamation-triangle fa-lg"/>
        <span t-esc="state.error"/>
    </div>

    <!-- Coordonnées manuelles + GPS -->
    <div class="row g-2 mb-3">
        <div class="col-md-5">
            <div class="input-group input-group-sm">
                <span class="input-group-text">
                    <i class="fa fa-map-marker text-danger me-1"/>Lat
                </span>
                <input type="number"
                       class="form-control"
                       step="0.0000001"
                       t-att-value="state.lat"
                       t-on-change="onLatChange"/>
            </div>
        </div>
        <div class="col-md-5">
            <div class="input-group input-group-sm">
                <span class="input-group-text">
                    <i class="fa fa-map-marker text-primary me-1"/>Lon
                </span>
                <input type="number"
                       class="form-control"
                       step="0.0000001"
                       t-att-value="state.lon"
                       t-on-change="onLonChange"/>
            </div>
        </div>
        <div class="col-md-2">
            <button class="btn btn-sm btn-outline-secondary w-100"
                    title="Utiliser ma position GPS"
                    t-on-click="onLocateMe">
                <i class="fa fa-crosshairs me-1"/>GPS
            </button>
        </div>
    </div>

    <!-- Aperçu carte (iframe OpenStreetMap) -->
    <div class="card border-0 shadow-sm rounded-3 overflow-hidden mb-2">
        <div class="card-header bg-light py-2 px-3 d-flex align-items-center justify-content-between">
            <span class="small fw-semibold text-muted">
                <i class="fa fa-map me-1"/>Aperçu de la position
            </span>
            <a t-att-href="state.mapsUrl"
               target="_blank"
               class="btn btn-sm btn-outline-secondary">
                <i class="fa fa-external-link me-1"/>Google Maps
            </a>
        </div>
        <iframe t-att-src="state.osmUrl"
                style="width:100%;height:360px;border:none;display:block;"
                frameborder="0"
                allowfullscreen="true"
                loading="lazy"/>
    </div>

    <p class="text-muted small mb-0">
        <i class="fa fa-info-circle me-1"/>
        Recherchez une adresse ou saisissez les coordonnées. La carte se met à jour automatiquement.
    </p>

</div>
`;

// ── Composant OWL ─────────────────────────────────────────────────────────────

export class MapPickerField extends Component {
    static template = MAP_TEMPLATE;

    static props = {
        ...standardFieldProps,
        lat_field: { type: String, optional: true },
        lon_field: { type: String, optional: true },
    };

    static defaultProps = {
        lat_field: "pharmacie_lat",
        lon_field: "pharmacie_lon",
    };

    setup() {
        const lat = this._readField(this.props.lat_field, 36.8065);
        const lon = this._readField(this.props.lon_field, 10.1815);

        this.state = useState({
            lat,
            lon,
            query:     "",
            searching: false,
            error:     null,
            osmUrl:    this._osmUrl(lat, lon),
            mapsUrl:   this._mapsUrl(lat, lon),
        });
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    _readField(field, fallback) {
        const v = this.props.record.data[field];
        return (v && v !== 0) ? parseFloat(v) : fallback;
    }

    _osmUrl(lat, lon) {
        return (
            `https://www.openstreetmap.org/export/embed.html` +
            `?bbox=${lon - 0.01},${lat - 0.01},${lon + 0.01},${lat + 0.01}` +
            `&layer=mapnik&marker=${lat},${lon}`
        );
    }

    _mapsUrl(lat, lon) {
        return `https://www.google.com/maps?q=${lat},${lon}`;
    }

    _commit(lat, lon) {
        const rLat = Math.round(lat * 1e7) / 1e7;
        const rLon = Math.round(lon * 1e7) / 1e7;
        this.state.lat    = rLat;
        this.state.lon    = rLon;
        this.state.osmUrl  = this._osmUrl(rLat, rLon);
        this.state.mapsUrl = this._mapsUrl(rLat, rLon);
        this.props.record.update({
            [this.props.lat_field]: rLat,
            [this.props.lon_field]: rLon,
        });
    }

    // ── Saisie manuelle ───────────────────────────────────────────────────────

    onLatChange(ev) {
        const v = parseFloat(ev.target.value);
        if (!isNaN(v)) this._commit(v, this.state.lon);
    }

    onLonChange(ev) {
        const v = parseFloat(ev.target.value);
        if (!isNaN(v)) this._commit(this.state.lat, v);
    }

    // ── Recherche Nominatim (OSM, gratuit, sans API key) ─────────────────────

    async onSearch() {
        const q = this.state.query.trim();
        if (!q) return;
        this.state.searching = true;
        this.state.error     = null;
        try {
            const resp = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`,
                { headers: { "Accept-Language": "fr" } }
            );
            const data = await resp.json();
            if (!data.length) {
                this.state.error = "Adresse introuvable. Essayez avec plus de détails.";
                return;
            }
            this._commit(parseFloat(data[0].lat), parseFloat(data[0].lon));
        } catch {
            this.state.error = "Erreur réseau. Vérifiez votre connexion.";
        } finally {
            this.state.searching = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter") this.onSearch();
    }

    // ── Géolocalisation navigateur ────────────────────────────────────────────

    onLocateMe() {
        if (!navigator.geolocation) {
            this.state.error = "Géolocalisation non supportée par ce navigateur.";
            return;
        }
        navigator.geolocation.getCurrentPosition(
            ({ coords }) => this._commit(coords.latitude, coords.longitude),
            ()           => { this.state.error = "Impossible d'obtenir votre position GPS."; }
        );
    }
}

// ── Enregistrement ────────────────────────────────────────────────────────────

registry.category("fields").add("map_picker", {
    component: MapPickerField,
    supportedTypes: ["float"],
    extractProps: ({ attrs }) => ({
        lat_field: attrs.lat_field || "pharmacie_lat",
        lon_field: attrs.lon_field || "pharmacie_lon",
    }),
});