import 'dart:math' as math;

typedef RetryPredicate = bool Function(Object error);

/// Bounded exponential backoff without hidden jitter.
final class RetryPolicy {
  const RetryPolicy({
    this.maxAttempts = 3,
    this.baseDelay = const Duration(milliseconds: 250),
    this.maxDelay = const Duration(seconds: 4),
    this.shouldRetry = _retryEverything,
  }) : assert(maxAttempts > 0);

  final int maxAttempts;
  final Duration baseDelay;
  final Duration maxDelay;
  final RetryPredicate shouldRetry;

  Duration delayBeforeAttempt(int nextAttempt) {
    if (nextAttempt <= 1) return Duration.zero;
    final int multiplier = math.pow(2, nextAttempt - 2).toInt();
    final int milliseconds = math.min(
      baseDelay.inMilliseconds * multiplier,
      maxDelay.inMilliseconds,
    );
    return Duration(milliseconds: milliseconds);
  }

  static bool _retryEverything(Object _) => true;
}
