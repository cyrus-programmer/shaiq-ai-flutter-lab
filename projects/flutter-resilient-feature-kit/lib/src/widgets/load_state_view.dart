import 'package:flutter/material.dart';

import '../core/load_state.dart';

typedef DataViewBuilder<T> = Widget Function(BuildContext context, T data);
typedef ErrorViewBuilder = Widget Function(
  BuildContext context,
  Object error,
  VoidCallback retry,
);

/// Maps every [LoadState] to an accessible Material UI without blank screens.
final class LoadStateView<T> extends StatelessWidget {
  const LoadStateView({
    required this.state,
    required this.dataBuilder,
    required this.onRetry,
    this.isEmpty,
    this.initialBuilder,
    this.loadingBuilder,
    this.emptyBuilder,
    this.errorBuilder,
    super.key,
  });

  final LoadState<T> state;
  final DataViewBuilder<T> dataBuilder;
  final VoidCallback onRetry;
  final bool Function(T data)? isEmpty;
  final WidgetBuilder? initialBuilder;
  final WidgetBuilder? loadingBuilder;
  final WidgetBuilder? emptyBuilder;
  final ErrorViewBuilder? errorBuilder;

  @override
  Widget build(BuildContext context) {
    final LoadState<T> current = state;
    if (current is LoadIdle<T>) {
      return initialBuilder?.call(context) ?? const SizedBox.shrink();
    }
    if (current is LoadInProgress<T>) {
      if (current.previous == null) {
        return loadingBuilder?.call(context) ??
            const Center(child: CircularProgressIndicator());
      }
      return _DataWithStatus<T>(
        data: current.previous as T,
        dataBuilder: dataBuilder,
        label: 'Refreshing',
        progress: true,
      );
    }
    if (current is LoadFailure<T>) {
      if (current.previous != null) {
        return _DataWithStatus<T>(
          data: current.previous as T,
          dataBuilder: dataBuilder,
          label: 'Could not refresh. Showing saved data.',
          progress: false,
        );
      }
      return errorBuilder?.call(context, current.error, onRetry) ??
          _DefaultError(error: current.error, onRetry: onRetry);
    }
    final LoadSuccess<T> success = current as LoadSuccess<T>;
    if (isEmpty?.call(success.data) ?? false) {
      return emptyBuilder?.call(context) ??
          const Center(child: Text('Nothing here yet.'));
    }
    if (success.isStale) {
      return _DataWithStatus<T>(
        data: success.data,
        dataBuilder: dataBuilder,
        label: 'Showing saved data',
        progress: false,
      );
    }
    return dataBuilder(context, success.data);
  }
}

final class _DataWithStatus<T> extends StatelessWidget {
  const _DataWithStatus({
    required this.data,
    required this.dataBuilder,
    required this.label,
    required this.progress,
  });

  final T data;
  final DataViewBuilder<T> dataBuilder;
  final String label;
  final bool progress;

  @override
  Widget build(BuildContext context) => Stack(
        fit: StackFit.passthrough,
        children: <Widget>[
          dataBuilder(context, data),
          Align(
            alignment: Alignment.topCenter,
            child: Semantics(
              liveRegion: true,
              label: label,
              child: progress
                  ? const LinearProgressIndicator()
                  : Material(
                      color: Theme.of(context).colorScheme.surfaceContainerHigh,
                      child: SizedBox(
                        width: double.infinity,
                        child: Padding(
                          padding: const EdgeInsets.all(8),
                          child: Text(label, textAlign: TextAlign.center),
                        ),
                      ),
                    ),
            ),
          ),
        ],
      );
}

final class _DefaultError extends StatelessWidget {
  const _DefaultError({required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(Icons.cloud_off_outlined, size: 40),
              const SizedBox(height: 12),
              Text('Unable to load data', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(error.toString(), textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(onPressed: onRetry, child: const Text('Try again')),
            ],
          ),
        ),
      );
}
