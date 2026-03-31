export function SkeletonCard({ className = "" }) {
  return (
    <div className={`bg-surface-800 border border-surface-700 rounded-xl overflow-hidden animate-pulse ${className}`}>
      <div className="aspect-square bg-surface-700" />
      <div className="p-3 space-y-2">
        <div className="h-3 bg-surface-700 rounded w-16" />
        <div className="h-3 bg-surface-600 rounded w-24" />
      </div>
    </div>
  );
}

export function SkeletonRow({ className = "" }) {
  return (
    <div className={`bg-surface-800 border border-surface-700 rounded-lg h-14 animate-pulse ${className}`} />
  );
}

export function SkeletonProductCard() {
  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 animate-pulse">
      <div className="h-4 bg-surface-700 rounded w-2/3 mb-3" />
      <div className="h-3 bg-surface-700 rounded w-1/3 mb-4" />
      <div className="flex gap-2">
        <div className="h-7 bg-surface-700 rounded w-20" />
        <div className="h-7 bg-surface-700 rounded w-20" />
        <div className="h-7 bg-surface-700 rounded w-14" />
      </div>
    </div>
  );
}

export function SkeletonSEOCard() {
  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 animate-pulse space-y-3">
      <div className="h-3 bg-surface-700 rounded w-24" />
      <div className="h-4 bg-surface-700 rounded w-full" />
      <div className="h-20 bg-surface-600 rounded w-full" />
      <div className="flex gap-1 flex-wrap">
        {[1,2,3,4].map(i => <div key={i} className="h-5 bg-surface-700 rounded w-16" />)}
      </div>
    </div>
  );
}
