import SwiftUI
import AVKit
import AVFoundation
import Combine

// SYN_NATIVE_AIRPLAY_796
// macOS 15+/Swift 6.4: no usar propiedades de AVKit/AVFoundation marcadas
// unavailable en el SDK macOS (usesExternalPlaybackWhileExternalScreenIsActive,
// prioritizesVideoDevices, activeTintColor).
// AirPlay real mediante AVPlayer, independiente del canvas VLCKit.
// VLC sigue siendo el reproductor principal; el cambio a AVPlayer solo ocurre
// después de solicitar AirPlay explícitamente.
@MainActor
final class SYNAirPlayPlayback796: ObservableObject {
    @Published private(set) var externalActive = false
    @Published private(set) var message = ""
    @Published private(set) var nativePlaying = false
    private(set) var player: AVPlayer?
    private(set) var hadExternalRoute = false

    func begin(_ source: URL) {
        stop()
        guard let scheme = source.scheme?.lowercased(), ["http", "https"].contains(scheme) else {
            message = "AirPlay requiere una URL HTTP(S) compatible con AVPlayer."
            return
        }
        // Xtream suele proporcionar .ts para VLC. Cuando se ofrece HLS,
        // AVPlayer puede reproducirlo; nunca alterar la URL original de VLC.
        let suffix = source.pathExtension.lowercased()
        var nativeURL = source
        if suffix == "ts" {
            nativeURL = source.deletingPathExtension().appendingPathExtension("m3u8")
            message = "Probando la variante HLS del canal. El proveedor debe admitirla."
        } else if suffix == "m3u8" || suffix == "mp4" {
            message = "Selecciona tu televisor en el menú AirPlay."
        } else {
            message = "AVPlayer intentará reproducir esta dirección; el proveedor debe ofrecer vídeo compatible."
        }
        let av = AVPlayer(url: nativeURL)
        av.allowsExternalPlayback = true
        // No hay emisión ni audio locales mientras se elige el receptor.
        // Al establecerse AirPlay se recupera el audio en el televisor.
        av.isMuted = true
        av.actionAtItemEnd = .none
        player = av
        nativePlaying = true
        av.play()
    }

    func refresh() {
        guard let av = player else { return }
        let nowExternal = av.isExternalPlaybackActive
        if nowExternal {
            hadExternalRoute = true
            av.isMuted = false
        }
        if externalActive != nowExternal { externalActive = nowExternal }
        if av.currentItem?.status == .failed {
            message = av.currentItem?.error?.localizedDescription
                ?? "Este canal no se puede reproducir con AVPlayer. Prueba una fuente HLS."
            av.pause()
            nativePlaying = false
        } else if nowExternal {
            message = "Emisión a través de AirPlay"
        }
    }

    func stop() {
        player?.pause()
        player?.replaceCurrentItem(with: nil)
        player = nil
        externalActive = false
        nativePlaying = false
        hadExternalRoute = false
        message = ""
    }
}

// Selector OFICIAL de Apple, asociado explícitamente a nuestro AVPlayer.
struct SYNAirPlayRoute796: NSViewRepresentable {
    let player: AVPlayer?
    func makeNSView(context: Context) -> AVRoutePickerView {
        let view = AVRoutePickerView(frame: NSRect(x: 0, y: 0, width: 40, height: 34))
        view.player = player
        // El selector AppKit hereda el tema CLARO de la ventana original.
        // Forzamos apariencia oscura y color blanco: contraste legible sobre negro.
        view.appearance = NSAppearance(named: .darkAqua)
        view.setRoutePickerButtonColor(.white, for: .normal)
        return view
    }
    func updateNSView(_ view: AVRoutePickerView, context: Context) {
        view.player = player
        view.appearance = NSAppearance(named: .darkAqua)
        view.setRoutePickerButtonColor(.white, for: .normal)
    }
}

private struct SYNAirPlayVideo796: NSViewRepresentable {
    let player: AVPlayer?
    func makeNSView(context: Context) -> AVPlayerView {
        let view = AVPlayerView(frame: .zero)
        view.player = player
        view.controlsStyle = .none
        view.videoGravity = .resizeAspect
        return view
    }
    func updateNSView(_ view: AVPlayerView, context: Context) {
        view.player = player
    }
}

// SYN_AIRPLAY_FULLSCREEN_797: sin ventana modal ni AVPlayerView adicional.
// Solo un panel de control dentro del Space fullscreen existente.
struct SYNFullscreenAirPlayPanel797: View {
    @ObservedObject var session: SYNAirPlayPlayback796
    let channel: String
    let onStop: () -> Void
    let onExit: () -> Void

    var body: some View {
        ZStack {
            Color.black
            VStack(spacing: 24) {
                Image(systemName: session.externalActive ? "airplayvideo.circle.fill" : "airplayvideo")
                    .font(.system(size: 58, weight: .ultraLight))
                    .foregroundStyle(.white.opacity(0.85))
                VStack(spacing: 8) {
                    Text(session.externalActive ? "Emitiendo por AirPlay" : "Enviar a un dispositivo")
                        .font(.system(size: 28, weight: .semibold))
                    Text(channel)
                        .font(.system(size: 15))
                        .foregroundStyle(.white.opacity(0.65))
                        .lineLimit(1)
                }
                .foregroundStyle(.white)
                HStack(spacing: 14) {
                    // AVRoutePickerView muestra directamente los dispositivos
                    // que macOS detecta; Apple no ofrece API pública para abrir
                    // automáticamente el menú de rutas sin interacción.
                    SYNAirPlayRoute796(player: session.player)
                        .frame(width: 48, height: 44)
                        .background(.white.opacity(0.17), in: RoundedRectangle(cornerRadius: 12))
                        .help("Elegir televisor o Apple TV")
                    Text(session.externalActive ? "Dispositivo conectado" : "Selecciona un dispositivo con el icono AirPlay")
                        .font(.system(size: 13))
                        .foregroundStyle(.white.opacity(0.86))
                }
                if !session.message.isEmpty {
                    Text(session.message)
                        .font(.system(size: 12))
                        .foregroundStyle(.white.opacity(0.58))
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: 440)
                }
                HStack(spacing: 16) {
                    Button("Volver a SYN", action: onStop)
                        .buttonStyle(.borderedProminent)
                    Button("Salir de pantalla completa", action: onExit)
                        .buttonStyle(.bordered)
                }
                .controlSize(.large)
            }
            .padding(38)
            .frame(maxWidth: 580)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .preferredColorScheme(.dark)
    }
}
