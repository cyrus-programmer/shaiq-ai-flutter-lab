/// The complete lifecycle of one asynchronously loaded value.
sealed class LoadState<T> {
  const LoadState();

  /// The most recently usable value, including stale and rollback data.
  T? get dataOrNull {
    final LoadState<T> current = this;
    if (current is LoadSuccess<T>) return current.data;
    if (current is LoadInProgress<T>) return current.previous;
    if (current is LoadFailure<T>) return current.previous;
    return null;
  }

  bool get hasData => dataOrNull != null;
}

final class LoadIdle<T> extends LoadState<T> {
  const LoadIdle();
}

final class LoadInProgress<T> extends LoadState<T> {
  const LoadInProgress({this.previous});

  final T? previous;
}

final class LoadSuccess<T> extends LoadState<T> {
  const LoadSuccess(this.data, {this.isStale = false});

  final T data;
  final bool isStale;
}

final class LoadFailure<T> extends LoadState<T> {
  const LoadFailure(this.error, this.stackTrace, {this.previous});

  final Object error;
  final StackTrace stackTrace;
  final T? previous;
}
