import 'dart:async';

import 'package:flutter/foundation.dart';

import '../cache/cache_store.dart';
import '../core/load_state.dart';
import '../core/retry_policy.dart';
import '../network/request_coalescer.dart';

typedef Fetcher<T> = Future<T> Function();
typedef Sleeper = Future<void> Function(Duration duration);

/// Owns loading, cache refresh, retry, optimistic updates, and disposal safety.
final class QueryController<T> extends ChangeNotifier {
  QueryController({
    required Fetcher<T> fetcher,
    required this.cacheKey,
    this.cacheStore,
    this.cacheTimeToLive = const Duration(minutes: 5),
    this.retryPolicy = const RetryPolicy(),
    RequestCoalescer<String, T>? coalescer,
    Clock? clock,
    Sleeper? sleeper,
  })  : _fetcher = fetcher,
        _coalescer = coalescer ?? RequestCoalescer<String, T>(),
        _clock = clock ?? DateTime.now,
        _sleeper = sleeper ?? Future<void>.delayed;

  final Fetcher<T> _fetcher;
  final String cacheKey;
  final CacheStore? cacheStore;
  final Duration cacheTimeToLive;
  final RetryPolicy retryPolicy;
  final RequestCoalescer<String, T> _coalescer;
  final Clock _clock;
  final Sleeper _sleeper;

  LoadState<T> _state = LoadIdle<T>();
  int _generation = 0;
  bool _disposed = false;

  LoadState<T> get state => _state;

  Future<void> load({bool forceRefresh = false}) async {
    final int generation = ++_generation;
    T? previous = _state.dataOrNull;

    final CacheEntry<T>? cached = await cacheStore?.read<T>(cacheKey);
    if (!_isCurrent(generation)) return;

    if (cached != null) {
      previous = cached.value;
      final bool expired = cached.isExpired(cacheTimeToLive, _clock());
      _emit(LoadSuccess<T>(cached.value, isStale: expired));
      if (!forceRefresh && !expired) return;
    }

    _emit(LoadInProgress<T>(previous: previous));
    try {
      final T value = await _coalescer.run(cacheKey, _fetchWithRetry);
      if (!_isCurrent(generation)) return;
      await cacheStore?.write<T>(
        cacheKey,
        CacheEntry<T>(value: value, savedAt: _clock()),
      );
      if (!_isCurrent(generation)) return;
      _emit(LoadSuccess<T>(value));
    } on Object catch (error, stackTrace) {
      if (!_isCurrent(generation)) return;
      _emit(LoadFailure<T>(error, stackTrace, previous: previous));
    }
  }

  Future<void> refresh() => load(forceRefresh: true);

  /// Applies immediately, then commits or rolls back while retaining the error.
  Future<bool> replaceOptimistically(
    T optimisticValue,
    Future<T> Function() commit,
  ) async {
    final int generation = ++_generation;
    final T? previous = _state.dataOrNull;
    _emit(LoadSuccess<T>(optimisticValue));
    try {
      final T confirmed = await commit();
      if (!_isCurrent(generation)) return false;
      await cacheStore?.write<T>(
        cacheKey,
        CacheEntry<T>(value: confirmed, savedAt: _clock()),
      );
      if (!_isCurrent(generation)) return false;
      _emit(LoadSuccess<T>(confirmed));
      return true;
    } on Object catch (error, stackTrace) {
      if (!_isCurrent(generation)) return false;
      _emit(LoadFailure<T>(error, stackTrace, previous: previous));
      return false;
    }
  }

  Future<T> _fetchWithRetry() async {
    int attempt = 1;
    while (true) {
      try {
        return await _fetcher();
      } on Object catch (error) {
        if (attempt >= retryPolicy.maxAttempts ||
            !retryPolicy.shouldRetry(error)) {
          rethrow;
        }
        attempt += 1;
        await _sleeper(retryPolicy.delayBeforeAttempt(attempt));
      }
    }
  }

  bool _isCurrent(int generation) => !_disposed && generation == _generation;

  void _emit(LoadState<T> next) {
    if (_disposed) return;
    _state = next;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _generation += 1;
    super.dispose();
  }
}
