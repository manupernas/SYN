import SwiftUI
import AppKit

// SYN 7.8: vistas puramente visuales; no modifican VLCKit, Xtream ni DVR.

/// Avatar determinista. El nombre (longitud, tipo y orden de letras) determina
/// icono y color. No usa hashValue (cambia entre procesos) ni datos externos.
struct SYNProfileAvatar78: View {
    let name: String
    var size: CGFloat = 36

    private static let symbols = [
        "tv", "dot.radiowaves.left.and.right", "play.rectangle.fill", "sparkles.tv",
        "film.stack.fill", "antenna.radiowaves.left.and.right", "waveform",
        "square.stack.3d.up.fill", "play.square.stack.fill", "circle.hexagongrid.fill",
        "bolt.horizontal.fill", "globe.europe.africa.fill", "hifispeaker.fill",
        "rectangle.stack.fill", "video.fill", "star.fill"
    ]
    private static let tones: [Color] = [
        Color(red: 0.16, green: 0.54, blue: 0.69),
        Color(red: 0.56, green: 0.35, blue: 0.75),
        Color(red: 0.83, green: 0.40, blue: 0.40),
        Color(red: 0.10, green: 0.59, blue: 0.51),
        Color(red: 0.76, green: 0.46, blue: 0.18),
        Color(red: 0.35, green: 0.47, blue: 0.76),
        Color(red: 0.62, green: 0.40, blue: 0.60),
        Color(red: 0.34, green: 0.58, blue: 0.37)
    ]

    private var stableCode: UInt64 {
        let normalized = name.precomposedStringWithCanonicalMapping
        var hash: UInt64 = 14_695_981_039_346_656_037
        for (position, scalar) in normalized.unicodeScalars.enumerated() {
            let value = scalar.value
            let type: UInt64
            if CharacterSet.decimalDigits.contains(scalar) { type = 5 }
            else if CharacterSet.uppercaseLetters.contains(scalar) { type = 3 }
            else if CharacterSet.lowercaseLetters.contains(scalar) { type = 2 }
            else if CharacterSet.letters.contains(scalar) { type = 7 }
            else { type = 11 }
            hash = (hash ^ (UInt64(value) &+ type &* 31 &+ UInt64(position))) &* 1_099_511_628_211
        }
        return hash ^ (UInt64(normalized.count) &* 1_140_071_481_932_319_849)
    }

    var body: some View {
        let code = stableCode
        ZStack {
            Circle().fill(Self.tones[Int(code % UInt64(Self.tones.count))])
            Image(systemName: Self.symbols[Int((code >> 13) % UInt64(Self.symbols.count))])
                .font(.system(size: size * 0.43, weight: .semibold))
                .foregroundStyle(.white)
                .symbolRenderingMode(.monochrome)
        }
        .frame(width: size, height: size)
        .accessibilityLabel("Icono del perfil \(name)")
    }
}

/// Material nativo. Fondo sólido para quien use Reducir transparencia.
struct SYNGlassCard78: ViewModifier {
    var corner: CGFloat = 16
    @Environment(\.accessibilityReduceTransparency) private var reduced
    func body(content: Content) -> some View {
        Group {
            if reduced {
                content.background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: corner))
            } else if #available(macOS 26, *) {
                content.glassEffect(.regular, in: .rect(cornerRadius: corner))
            } else {
                content.background(.regularMaterial, in: RoundedRectangle(cornerRadius: corner))
            }
        }
    }
}

struct SYNSidebarSelection78: ViewModifier {
    let selected: Bool
    @Environment(\.accessibilityReduceTransparency) private var reduced
    func body(content: Content) -> some View {
        Group {
            if selected {
                if reduced {
                    content.background(Color(nsColor: .selectedContentBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
                } else if #available(macOS 26, *) {
                    content.glassEffect(.regular, in: .rect(cornerRadius: 12))
                } else {
                    content.background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            } else { content }
        }
    }
}

/// Colorea el cristal con el tono existente de cada programa, sin modificar
/// la identidad de color de la EPG ni su posición horaria.
// SYN_EPG_CONTRAST_781 — conserva el color original, sin lavarlo con glassEffect.
// La barra lateral y los controles sí emplean cristal nativo; los programas
// necesitan contraste y colores legibles sobre la parrilla.
struct SYNEPGGlass78: ViewModifier {
    let tint: Color
    let enabled: Bool

    func body(content: Content) -> some View {
        content
            .background(tint, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .overlay {
                if enabled {
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .strokeBorder(.white.opacity(0.20), lineWidth: 1)
                        .allowsHitTesting(false)
                }
            }
            .shadow(color: .black.opacity(enabled ? 0.13 : 0), radius: 2, y: 1)
    }
}
