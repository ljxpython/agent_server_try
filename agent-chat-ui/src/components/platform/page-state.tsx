import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type PageStateProps = {
  message: ReactNode;
  className?: string;
  testId: "state-loading" | "state-empty" | "state-error" | "state-notice";
};

function PageState({ message, className, testId }: PageStateProps) {
  return (
    <p
      data-testid={testId}
      className={cn("mt-4 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm", className)}
    >
      {message}
    </p>
  );
}

type PageStateMessageProps = {
  message?: ReactNode;
  className?: string;
};

export function PageStateLoading({ message = "Loading...", className }: PageStateMessageProps) {
  return <PageState testId="state-loading" message={message} className={cn("text-muted-foreground", className)} />;
}

export function PageStateEmpty({ message, className }: PageStateMessageProps) {
  return <PageState testId="state-empty" message={message ?? "No data found."} className={cn("text-muted-foreground", className)} />;
}

export function PageStateError({ message, className }: PageStateMessageProps) {
  return <PageState testId="state-error" message={message ?? "Something went wrong."} className={cn("border-destructive/40 bg-destructive/10 text-destructive", className)} />;
}

export function PageStateNotice({ message, className }: PageStateMessageProps) {
  return <PageState testId="state-notice" message={message ?? "Done."} className={cn("border-primary/30 bg-primary/10 text-foreground", className)} />;
}
