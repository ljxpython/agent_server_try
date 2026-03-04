"use client";

import { PageStateNotice } from "@/components/platform/page-state";

export default function RuntimeBindingsPage() {
  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Environments</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        Environment mappings are deprecated and managed automatically.
      </p>
      <PageStateNotice
        className="mt-4"
        message="Read-only notice: mappings are no longer editable on this page."
      />
    </section>
  );
}
