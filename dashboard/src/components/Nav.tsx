import { Button } from "@/components/ui/button"

export function Nav() {
  return (
    <header className="flex items-center justify-between">
      <a href="#/" className="flex items-center gap-2 font-semibold">
        <img src="/icon.svg" alt="" className="size-7" />
        Creeping Hunger
      </a>
      <nav className="flex gap-2">
        <Button variant="ghost" asChild><a href="#/">About</a></Button>
        <Button variant="outline" asChild><a href="#/dashboard">Dashboard</a></Button>
      </nav>
    </header>
  )
}
