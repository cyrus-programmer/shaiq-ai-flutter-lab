/// Shares one in-flight request between callers using the same key.
final class RequestCoalescer<K, V> {
  final Map<K, Future<V>> _inFlight = <K, Future<V>>{};

  int get pendingCount => _inFlight.length;

  Future<V> run(K key, Future<V> Function() operation) {
    final Future<V>? existing = _inFlight[key];
    if (existing != null) return existing;

    final Future<V> future = Future<V>.sync(operation);
    _inFlight[key] = future;

    void clear() {
      if (identical(_inFlight[key], future)) _inFlight.remove(key);
    }

    future.then<void>((V _) => clear(), onError: (Object _, StackTrace __) => clear());
    return future;
  }
}
