import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:resilient_feature_kit/resilient_feature_kit.dart';

void main() {
  group('RetryPolicy', () {
    test('uses bounded exponential delays', () {
      const RetryPolicy policy = RetryPolicy(
        baseDelay: Duration(milliseconds: 100),
        maxDelay: Duration(milliseconds: 250),
      );
      expect(policy.delayBeforeAttempt(1), Duration.zero);
      expect(policy.delayBeforeAttempt(2), const Duration(milliseconds: 100));
      expect(policy.delayBeforeAttempt(3), const Duration(milliseconds: 200));
      expect(policy.delayBeforeAttempt(4), const Duration(milliseconds: 250));
    });
  });

  group('MemoryCacheStore', () {
    test('round trips typed values', () async {
      final MemoryCacheStore cache = MemoryCacheStore();
      final DateTime savedAt = DateTime.utc(2026, 8, 25);
      await cache.write<int>('count', CacheEntry<int>(value: 4, savedAt: savedAt));
      final CacheEntry<int>? result = await cache.read<int>('count');
      expect(result?.value, 4);
      expect(result?.savedAt, savedAt);
    });

    test('drops a value requested with the wrong type', () async {
      final MemoryCacheStore cache = MemoryCacheStore();
      await cache.write<int>(
        'value',
        CacheEntry<int>(value: 4, savedAt: DateTime.utc(2026)),
      );
      expect(await cache.read<String>('value'), isNull);
      expect(await cache.read<int>('value'), isNull);
    });

    test('entry expires at its exact time to live', () {
      final DateTime savedAt = DateTime.utc(2026, 8, 25, 8);
      final CacheEntry<int> entry = CacheEntry<int>(value: 1, savedAt: savedAt);
      expect(entry.isExpired(const Duration(minutes: 5), savedAt.add(const Duration(minutes: 4))), isFalse);
      expect(entry.isExpired(const Duration(minutes: 5), savedAt.add(const Duration(minutes: 5))), isTrue);
    });
  });

  test('RequestCoalescer shares and then clears an in-flight request', () async {
    final RequestCoalescer<String, int> coalescer = RequestCoalescer<String, int>();
    final Completer<int> completer = Completer<int>();
    int calls = 0;
    Future<int> operation() {
      calls += 1;
      return completer.future;
    }

    final Future<int> first = coalescer.run('catalogue', operation);
    final Future<int> second = coalescer.run('catalogue', operation);
    expect(identical(first, second), isTrue);
    expect(calls, 1);
    expect(coalescer.pendingCount, 1);
    completer.complete(7);
    expect(await second, 7);
    await Future<void>.delayed(Duration.zero);
    expect(coalescer.pendingCount, 0);
  });
}
