// Поддельный Фотошоп для проверки сценария экспорта PSD без самого Фотошопа.
// Запуск: node photoshop_mock.js build_psd.jsx  -> печатает JSON с тем, что сценарий сделал.
"use strict";
const fs = require("fs");
const vm = require("vm");

const state = { opened: [], closed: [], saved: null, layers: [], strokes: [], prefs: {} };

function enumOf(names) {
    const e = {};
    for (const n of names) e[n] = n;
    return e;
}

class TextItem {
    constructor() { this.kind = "POINTTEXT"; }
}

class ArtLayer {
    constructor(doc, name, isBackground) {
        this.doc = doc;
        this.name = name;
        this.visible = true;
        this.isBackgroundLayer = !!isBackground;
        this._kind = "NORMAL";
        this.textItem = null;
    }
    get kind() { return this._kind; }
    set kind(value) {
        this._kind = value;
        if (value === "TEXT") this.textItem = new TextItem();
    }
    duplicate(target) {
        const copy = new ArtLayer(target, this.name, false);
        copy.duplicatedFrom = this.doc.path;
        target.artLayers._items.unshift(copy);
        return copy;
    }
}

class Document {
    constructor(path) {
        this.path = path;
        const self = this;
        this.artLayers = {
            _items: [new ArtLayer(this, "Фон", true)],
            get length() { return this._items.length; },
            add() {
                const layer = new ArtLayer(self, "Слой", false);
                this._items.unshift(layer);
                state.layers.push(layer);
                self.activeLayer = layer;
                return layer;
            },
        };
        Object.defineProperty(this.artLayers, "0", { get() { return this._items[this._items.length - 1]; } });
        this.activeLayer = this.artLayers._items[0];
    }
    saveAs(file, options, asCopy, extension) {
        state.saved = { path: file.path, layersOption: options.layers, asCopy, extension,
                        stack: this.artLayers._items.map((l) => l.name) };
    }
    close(mode) { state.closed.push({ path: this.path, mode }); }
}

class File {
    constructor(path) { this.path = path; this.encoding = null; this._mode = null; }
    open(mode) { this._mode = mode; return true; }
    writeln(text) { fs.appendFileSync(this.path, text + "\n", "utf8"); }
    close() { this._mode = null; }
}

class SolidColor { constructor() { this.rgb = { red: -1, green: -1, blue: -1 }; } }
class PhotoshopSaveOptions { constructor() { this.layers = false; } }
class ActionDescriptor {
    constructor() { this.values = {}; }
    putReference(k, v) { this.values[k] = v; }
    putUnitDouble(k, unit, v) { this.values[k] = v; }
    putBoolean(k, v) { this.values[k] = v; }
    putEnumerated(k, t, v) { this.values[k] = v; }
    putDouble(k, v) { this.values[k] = v; }
    putObject(k, cls, v) { this.values[k] = v; }
}
class ActionReference { putProperty() {} putEnumerated() {} }

const app = {
    preferences: { rulerUnits: "CM", typeUnits: "POINTS" },
    displayDialogs: "ALL",
    activeDocument: null,
    open(file) {
        const doc = new Document(file.path);
        state.opened.push(file.path);
        app.activeDocument = doc;
        return doc;
    },
};

const sandbox = {
    app, File, SolidColor, PhotoshopSaveOptions, ActionDescriptor, ActionReference,
    LayerKind: enumOf(["TEXT", "NORMAL"]),
    Justification: enumOf(["CENTER", "LEFT"]),
    AntiAlias: enumOf(["SMOOTH", "SHARP"]),
    WarpStyle: enumOf(["ARC", "NONE"]),
    Direction: enumOf(["HORIZONTAL", "VERTICAL"]),
    ElementPlacement: enumOf(["PLACEATBEGINNING"]),
    SaveOptions: enumOf(["DONOTSAVECHANGES"]),
    Extension: enumOf(["LOWERCASE"]),
    Units: enumOf(["PIXELS"]),
    TypeUnits: enumOf(["PIXELS"]),
    DialogModes: enumOf(["NO", "ALL"]),
    charIDToTypeID: (id) => id,
    executeAction: (id, desc) => {
        const stroke = desc.values["T   "].values["FrFX"].values;
        state.strokes.push({ layer: state.layers.length - 1, size: stroke["Sz  "] });
    },
};

const source = fs.readFileSync(process.argv[2], "utf8").replace(/^﻿/, "").replace(/^#target.*$/m, "");
vm.runInNewContext(source, sandbox, { filename: "build_psd.jsx" });

state.prefs = { rulerUnits: app.preferences.rulerUnits, typeUnits: app.preferences.typeUnits,
                displayDialogs: app.displayDialogs };
state.layers = state.layers.map((l) => ({ kind: l.kind, text: l.textItem }));
console.log(JSON.stringify(state, (key, value) => (key === "doc" ? undefined : value)));
