import Foundation
import Security
import Combine

// Passwords are in macOS Keychain, NEVER UserDefaults, logs, or project files.
enum CredentialVault {
    private static let service = "com.mrseivane.SYNNative.xtream"
    static func save(password: String, id: UUID) throws {
        let key = id.uuidString
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: service,
                                    kSecAttrAccount as String: key]
        let data = Data(password.utf8)
        let updated = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if updated == errSecSuccess { return }
        guard updated == errSecItemNotFound else {
            throw NSError(domain: NSOSStatusErrorDomain, code: Int(updated))
        }
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(add as CFDictionary, nil)
        guard status == errSecSuccess else { throw NSError(domain: NSOSStatusErrorDomain, code: Int(status)) }
    }
    static func password(id: UUID) -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: service,
                                    kSecAttrAccount as String: id.uuidString,
                                    kSecMatchLimit as String: kSecMatchLimitOne,
                                    kSecReturnData as String: true]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func delete(id: UUID) {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword,
                       kSecAttrService as String: service,
                       kSecAttrAccount as String: id.uuidString] as CFDictionary)
    }
}

@MainActor final class ProfileStore: ObservableObject {
    @Published private(set) var profiles: [XtreamProfile] = []
    private let key = "syn.native.xtream.profiles.v1"
    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let decoded = try? JSONDecoder().decode([XtreamProfile].self, from: data) {
            profiles = decoded
        }
    }
    func append(_ profile: XtreamProfile, password: String) throws {
        try CredentialVault.save(password: password, id: profile.id)
        profiles.append(profile)
        persist()
    }
    @discardableResult
    func rename(_ id: UUID, to proposedName: String) -> XtreamProfile? {
        let clean = String(proposedName.trimmingCharacters(in: .whitespacesAndNewlines).prefix(60))
        guard !clean.isEmpty, let index = profiles.firstIndex(where: { $0.id == id }) else { return nil }
        profiles[index].name = clean
        persist()
        return profiles[index]
    }
    func update(_ profile: XtreamProfile, password: String?) throws {
        guard let index = profiles.firstIndex(where: { $0.id == profile.id }) else { return }
        if let password, !password.isEmpty {
            try CredentialVault.save(password: password, id: profile.id)
        }
        profiles[index] = profile  // ID intacto = favoritos intactos
        persist()
    }
    func delete(_ id: UUID) {
        profiles.removeAll { $0.id == id }
        CredentialVault.delete(id: id)
        persist()
    }
    private func persist() {
        guard let data = try? JSONEncoder().encode(profiles) else { return }
        UserDefaults.standard.set(data, forKey: key)
    }
}
