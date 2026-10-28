import SwiftUI

struct SYNTheme {
    enum Mood: String, CaseIterable, Identifiable { case coral = "Diurno · Coral", teal = "Nocturno · Teal"; var id: String { rawValue } }
    let mood: Mood
    var dark: Bool { mood == .teal }
    var background: Color { Color(hex: dark ? 0x061B1F : 0xFFF2EC) }
    var sidebar: Color { Color(hex: dark ? 0x0A2B30 : 0xF7A18D) }
    var panel: Color { Color(hex: dark ? 0x123239 : 0xFFE5DC) }
    var surface: Color { Color(hex: dark ? 0x183D41 : 0xFFFAF7) }
    var accent: Color { Color(hex: dark ? 0xFF8A29 : 0x59BEB6) }
    var foreground: Color { Color(hex: dark ? 0xF4F4F0 : 0x573D40) }
    var muted: Color { Color(hex: dark ? 0xA5C1BF : 0x95676A) }
}

extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: 1)
    }
}
