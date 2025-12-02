class t {
    constructor() {
        this.listeners = {}
    }

    on(t, e, s) {
        if (this.listeners[t] || (this.listeners[t] = new Set), null == s ? void 0 : s.once) {
            const s = (...i) => {
                this.un(t, s), e(...i)
            };
            return this.listeners[t].add(s), () => this.un(t, s)
        }
        return this.listeners[t].add(e), () => this.un(t, e)
    }

    un(t, e) {
        var s;
        null === (s = this.listeners[t]) || void 0 === s || s.delete(e)
    }

    once(t, e) {
        return this.on(t, e, {once: !0})
    }

    unAll() {
        this.listeners = {}
    }

    emit(t, ...e) {
        this.listeners[t] && this.listeners[t].forEach((t => t(...e)))
    }
}

class e extends t {
    constructor(t) {
        super(), this.subscriptions = [], this.isDestroyed = !1, this.options = t
    }

    onInit() {}

    _init(t) {
        this.isDestroyed && (this.subscriptions = [], this.isDestroyed = !1)
        this.wavesurfer = t
        this.onInit()
    }

    destroy() {
        this.emit("destroy")
        this.subscriptions.forEach((t => t()))
        this.subscriptions = []
        this.isDestroyed = !0
        this.wavesurfer = void 0
    }
}

function s(t, e) {
    const i = e.xmlns ? document.createElementNS(e.xmlns, t) : document.createElement(t)
    for (const [t, n] of Object.entries(e))
        if ("children" === t && n)
            for (const [t, e] of Object.entries(n))
                e instanceof Node ? i.appendChild(e)
                    : "string" == typeof e ? i.appendChild(document.createTextNode(e))
                    : i.appendChild(s(t, e))
        else "style" === t ? Object.assign(i.style, n)
            : "textContent" === t ? i.textContent = n
            : i.setAttribute(t, n.toString())
    return i
}

function i(t, e, i) {
    const n = s(t, e || {})
    return null == i || i.appendChild(n), n
}

const n = {
    lineWidth: 1,
    labelSize: 11,
    labelPreferLeft: !1,
    formatTimeCallback: t => `${Math.floor(t / 60)}:${`0${Math.floor(t) % 60}`.slice(-2)}`,
    getStats: null,
}

class o extends e {
    constructor(t) {
        super(t || {})
        this.lastPointerPosition = null
        this.unsubscribe = () => {}
        this.extraClones = []

        this.onPointerMove = t => {
            if (!this.wavesurfer) return
            this.lastPointerPosition = { clientX: t.clientX, clientY: t.clientY }
            const e = this.wavesurfer.getWrapper().getBoundingClientRect(),
                { width: s } = e,
                i = t.clientX - e.left,
                n = Math.min(1, Math.max(0, i / s)),
                posX = Math.min(s - this.options.lineWidth - 1, i)

            // main hover line
            this.wrapper.style.transform = `translateX(${posX}px)`
            this.wrapper.style.opacity = "1"

            // calculate main label
            const duration = this.wavesurfer.getDuration() || 0
            const timeSec = duration * n
            const timeText = this.options.formatTimeCallback(timeSec)

            if (this.options.getStats) {
                const { amplitude, pitch, intensity } = this.options.getStats(timeSec) || {}
                this.label.innerHTML =
                    `${timeText}<br>` +
                    `Amp: ${amplitude != null ? amplitude.toFixed(2) : '--'}<br>`
            } else {
                this.label.textContent = timeText
            }

            const labelWidth = this.label.offsetWidth
            const preferLeft = this.options.labelPreferLeft ? posX - labelWidth > 0 : posX + labelWidth > s
            this.label.style.transform = preferLeft
                ? `translateX(-${labelWidth + this.options.lineWidth}px)`
                : ""

            // Multi-container clones
            this.extraClones?.forEach(clone => {
                const container = clone.parentElement
                if (!container) return

                const mainRect = this.wavesurfer.getWrapper().getBoundingClientRect()
                const mainWidth = mainRect.width

                const containerRect = container.getBoundingClientRect()
                const containerOffsetLeft = containerRect.left - mainRect.left

                const unifiedX = Math.min(mainWidth - this.options.lineWidth - 1, t.clientX - mainRect.left)
                const relativeX = unifiedX - containerOffsetLeft

                clone.style.transform = `translateX(${relativeX}px)`
                clone.style.opacity = '1'

                const label = clone.querySelector('span')
                if (label) {
                    const relRatio = unifiedX / mainWidth
                    const cloneTime = duration * relRatio

                    if (this.options.getStats) {
                        const { pitch, intensity } = this.options.getStats(cloneTime) || {}
                        label.innerHTML =
                            `Pitch(Hz): ${pitch != null ? pitch.toFixed(2) : '--'}<br>` +
                            `Intensity(dB): ${intensity != null ? intensity.toFixed(2) : '--'}`
                    } else {
                        label.textContent = this.options.formatTimeCallback(cloneTime)
                    }

                    const labelW = label.offsetWidth
                    label.style.transform =
                        relativeX + labelW > containerRect.width
                            ? `translateX(-${labelW + this.options.lineWidth}px)`
                            : ''
                }
            })

            this.emit("hover", n)
        }

        this.onPointerLeave = () => {
            this.wrapper.style.opacity = "0"
            this.lastPointerPosition = null
            this.extraClones?.forEach(clone => {
                clone.style.opacity = '0'
            })
        }

        this.options = Object.assign({}, n, t)
        this.wrapper = i("div", { part: "hover" })
        this.label = i("span", { part: "hover-label" }, this.wrapper)
    }

    static create(t) {
        return new o(t)
    }

    addUnits(t) {
        return `${t}${"number" == typeof t ? "px" : ""}`
    }

    onInit() {
        if (!this.wavesurfer) throw Error("WaveSurfer is not initialized")
        const t = this.wavesurfer.options,
            e = this.options.lineColor || t.cursorColor || t.progressColor

        Object.assign(this.wrapper.style, {
            position: "absolute",
            zIndex: 10,
            left: 0,
            top: 0,
            height: "100%",
            pointerEvents: "none",
            borderLeft: `${this.addUnits(this.options.lineWidth)} solid ${e}`,
            opacity: "0",
            transition: "opacity .1s ease-in"
        })
        Object.assign(this.label.style, {
            display: "block",
            backgroundColor: this.options.labelBackground,
            color: this.options.labelColor,
            fontSize: `${this.addUnits(this.options.labelSize)}`,
            transition: "transform .1s ease-in",
            padding: "2px 3px"
        })

        const wrapper = this.wavesurfer.getWrapper()
        wrapper.appendChild(this.wrapper)

        const updateOnZoomScroll = () => {
            this.lastPointerPosition && this.onPointerMove(this.lastPointerPosition)
        }
        const zoomUnsub = this.wavesurfer.on("zoom", updateOnZoomScroll)
        const scrollUnsub = this.wavesurfer.on("scroll", updateOnZoomScroll)

        wrapper.addEventListener("pointermove", this.onPointerMove)
        wrapper.addEventListener("pointerleave", this.onPointerLeave)
        wrapper.addEventListener("wheel", this.onPointerMove)

        this.unsubscribe = () => {
            wrapper.removeEventListener("pointermove", this.onPointerMove)
            wrapper.removeEventListener("pointerleave", this.onPointerLeave)
            wrapper.removeEventListener("wheel", this.onPointerMove)
            zoomUnsub()
            scrollUnsub()
        }
    }

    attachToContainer(container) {
        const clone = this.wrapper.cloneNode(true)
        container.style.position = 'relative'
        container.appendChild(clone)
        this.extraClones.push(clone)
    }

    destroy() {
        super.destroy()
        this.unsubscribe()
        this.wrapper.remove()
    }
}

export { o as default }
