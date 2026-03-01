import { redirect } from "next/navigation";

export default function Page() {
  if ((process.env.NEXT_PUBLIC_OIDC_ENABLED ?? "false") === "true") {
    redirect("/auth/login");
  }

  redirect("/workspace/chat");
}
