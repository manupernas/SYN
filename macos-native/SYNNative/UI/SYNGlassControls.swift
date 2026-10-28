import AppKit
import SwiftUI

// SYN Glass Kit 6.0
// Independiente del reproductor: no accede a VLCKit ni al canvas.
enum SYNGlassKit {
    /// Material de macOS con adaptación automática a accesibilidad.
    static func panel(cornerRadius: CGFloat = 20) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = .hudWindow
        view.blendingMode = .behindWindow
        view.state = .active
        view.wantsLayer = true
        view.layer?.cornerRadius = cornerRadius
        view.layer?.masksToBounds = true
        return view
    }

    /// Botón AppKit para el HUD fullscreen actual.
    static func button(_ symbol: String, tip: String,
                       target: AnyObject?, action: Selector?) -> NSButton {
        let button = NSButton()
        button.bezelStyle = .accessoryBarAction
        button.isBordered = false
        button.image = NSImage(systemSymbolName: symbol, accessibilityDescription: tip)
        button.imagePosition = .imageOnly
        button.toolTip = tip
        button.target = target
        button.action = action
        button.translatesAutoresizingMaskIntoConstraints = false
        button.wantsLayer = true
        button.layer?.cornerRadius = 13
        button.contentTintColor = .labelColor
        NSLayoutConstraint.activate([
            button.widthAnchor.constraint(equalToConstant: 38),
            button.heightAnchor.constraint(equalToConstant: 38)
        ])
        return button
    }
}

/// Contenedor de controles que mantiene la interacción en sus hijos.
/// No debe instalarse por encima de toda la superficie de vídeo.
struct SYNGlassSurface<Content: View>: View {
    let content: Content
    var radius: CGFloat = 20

    init(radius: CGFloat = 20, @ViewBuilder content: () -> Content) {
        self.radius = radius
        self.content = content()
    }

    var body: some View {
        Group {
            if #available(macOS 26.0, *) {
                content
                    .padding(12)
                    .glassEffect(.regular, in: .rect(cornerRadius: radius))
            } else {
                content
                    .padding(12)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: radius))
            }
        }
    }
}

/// Estilo de botones SwiftUI usado por futuros paneles del fullscreen.
struct SYNGlassButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        Group {
            if #available(macOS 26.0, *) {
                configuration.label
                    .padding(10)
                    .glassEffect(.regular.interactive(), in: .capsule)
            } else {
                configuration.label
                    .padding(10)
                    .background(.regularMaterial, in: Capsule())
            }
        }
        .scaleEffect(configuration.isPressed ? 0.97 : 1)
        .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}
