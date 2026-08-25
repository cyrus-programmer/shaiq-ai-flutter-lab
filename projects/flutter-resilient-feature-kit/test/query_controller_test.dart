import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:resilient_feature_kit/resilient_feature_kit.dart';

void main() {
  final DateTime now = DateTime.utc(2026, 8, 25, 8);

  test('loads remote data and writes it to cache', () async {
    final MemoryCacheStore cache = MemoryCacheStore();
    final QueryController<String> controller = QueryController<String>(
      fetcher: () async => 'remote',
      cacheKey: 'profile',
      cacheStore: cache,
      clock: () => now,
    );
    await controller.load();
    expect((controller.state as LoadSuccess<String>).data, 'remote');
    expect((await cache.read<String>('profile'))?.value, 'remote');
  });

  test('fresh cache skips the fetcher', () async {
    final MemoryCacheStore cache = MemoryCacheStore();
    await cache.write<String>(
      'profile',
      CacheEntry<String>(value: 'cached', savedAt: now),
    );
    int calls = 0;
    final QueryController<String> controller = QueryController<String>(
      fetcher: () async { calls += 1; return 'remote'; },
      cacheKey: 'profile',
      cacheStore: cache,
      clock: () => now,
    );
    await controller.load();
    expect(calls, 0);
    expect((controller.state as LoadSuccess<String>).data, 'cached');
  });

  test('expired cache remains visible while remote refreshes', () async {
    final MemoryCacheStore cache = MemoryCacheStore();
    await cache.write<String>(
      'profile',
      CacheEntry<String>(value: 'stale', savedAt: now.subtract(const Duration(hours: 1))),
    );
    final Completer<String> remote = Completer<String>();
    final QueryController<String> controller = QueryController<String>(
      fetcher: () => remote.future,
      cacheKey: 'profile',
      cacheStore: cache,
      cacheTimeToLive: const Duration(minutes: 5),
      clock: () => now,
    );
    final Future<void> loading = controller.load();
    await Future<void>.delayed(Duration.zero);
    expect(controller.state, isA<LoadInProgress<String>>());
    expect(controller.state.dataOrNull, 'stale');
    remote.complete('fresh');
    await loading;
    expect((controller.state as LoadSuccess<String>).data, 'fresh');
  });

  test('retries with configured delay before succeeding', () async {
    int attempts = 0;
    final List<Duration> sleeps = <Duration>[];
    final QueryController<String> controller = QueryController<String>(
      fetcher: () async {
        attempts += 1;
        if (attempts < 3) throw StateError('temporary');
        return 'ok';
      },
      cacheKey: 'retry',
      retryPolicy: const RetryPolicy(
        maxAttempts: 3,
        baseDelay: Duration(milliseconds: 10),
      ),
      sleeper: (Duration duration) async => sleeps.add(duration),
    );
    await controller.load();
    expect(attempts, 3);
    expect(sleeps, <Duration>[const Duration(milliseconds: 10), const Duration(milliseconds: 20)]);
    expect(controller.state, isA<LoadSuccess<String>>());
  });

  test('preserves previous data when refresh fails', () async {
    int calls = 0;
    final QueryController<String> controller = QueryController<String>(
      fetcher: () async {
        calls += 1;
        if (calls == 1) return 'first';
        throw StateError('offline');
      },
      cacheKey: 'failure',
      retryPolicy: const RetryPolicy(maxAttempts: 1),
    );
    await controller.load();
    await controller.refresh();
    final LoadFailure<String> failure = controller.state as LoadFailure<String>;
    expect(failure.previous, 'first');
    expect(failure.error, isA<StateError>());
  });

  test('optimistic update commits confirmed value', () async {
    final QueryController<int> controller = QueryController<int>(
      fetcher: () async => 1,
      cacheKey: 'counter',
    );
    await controller.load();
    final Future<bool> updating = controller.replaceOptimistically(2, () async => 3);
    expect((controller.state as LoadSuccess<int>).data, 2);
    expect(await updating, isTrue);
    expect((controller.state as LoadSuccess<int>).data, 3);
  });

  test('optimistic update rolls back on failure', () async {
    final QueryController<int> controller = QueryController<int>(
      fetcher: () async => 1,
      cacheKey: 'counter',
    );
    await controller.load();
    final bool committed = await controller.replaceOptimistically(
      2,
      () async => throw StateError('rejected'),
    );
    expect(committed, isFalse);
    final LoadFailure<int> failure = controller.state as LoadFailure<int>;
    expect(failure.previous, 1);
  });

  test('dispose prevents a late request from emitting state', () async {
    final Completer<String> completer = Completer<String>();
    final QueryController<String> controller = QueryController<String>(
      fetcher: () => completer.future,
      cacheKey: 'late',
    );
    final Future<void> loading = controller.load();
    controller.dispose();
    completer.complete('too late');
    await loading;
    expect(controller.state, isNot(isA<LoadSuccess<String>>()));
  });
}
