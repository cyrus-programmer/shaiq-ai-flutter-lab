typedef Clock = DateTime Function();

final class CacheEntry<T> {
  const CacheEntry({required this.value, required this.savedAt});

  final T value;
  final DateTime savedAt;

  bool isExpired(Duration timeToLive, DateTime now) =>
      now.difference(savedAt) >= timeToLive;
}

abstract interface class CacheStore {
  Future<CacheEntry<T>?> read<T>(String key);
  Future<void> write<T>(String key, CacheEntry<T> entry);
  Future<void> remove(String key);
  Future<void> clear();
}

/// Process-local cache suitable for tests, prototypes, and session data.
final class MemoryCacheStore implements CacheStore {
  final Map<String, CacheEntry<Object?>> _entries = <String, CacheEntry<Object?>>{};

  @override
  Future<CacheEntry<T>?> read<T>(String key) async {
    final CacheEntry<Object?>? entry = _entries[key];
    if (entry == null) return null;
    if (entry.value is! T) {
      await remove(key);
      return null;
    }
    return CacheEntry<T>(value: entry.value as T, savedAt: entry.savedAt);
  }

  @override
  Future<void> write<T>(String key, CacheEntry<T> entry) async {
    _entries[key] = CacheEntry<Object?>(
      value: entry.value,
      savedAt: entry.savedAt,
    );
  }

  @override
  Future<void> remove(String key) async => _entries.remove(key);

  @override
  Future<void> clear() async => _entries.clear();
}
