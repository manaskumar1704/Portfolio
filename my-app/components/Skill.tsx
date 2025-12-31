type SkillProps = {
  icon: React.ReactNode;
  label: string;
  className?: string;
};

export default function Skill({ icon, label, className }: SkillProps) {
  return (
    <div className={`flex flex-col items-center gap-2 text-muted-foreground transition ${className || "hover:text-accent"}`}>
      <div className="text-3xl">{icon}</div>
      <span className="text-xs">{label}</span>
    </div>
  );
}
