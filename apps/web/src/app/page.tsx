import { AgentPanel } from "@/features/agent/agent-panel";
import { BootOverlay } from "@/features/shell/boot-overlay";
import { CrtOverlay } from "@/features/shell/crt-overlay";
import { Statusbar } from "@/features/shell/statusbar";
import { Topbar } from "@/features/shell/topbar";
import { ContactSection } from "@/features/contact/contact-section";
import { ProjectsSection } from "@/features/projects/projects-section";

export default function Page() {
  return (
    <>
      <CrtOverlay />
      <BootOverlay />
      <Topbar />
      <main>
        <AgentPanel />
        <div className="mx-auto w-[min(1000px,100%)] px-[clamp(14px,4vw,40px)]">
          <ProjectsSection />
          <ContactSection />
        </div>
      </main>
      <Statusbar />
    </>
  );
}
