export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 w-full h-[var(--navbar-height)] bg-black border-b border-zinc-800 z-40">
      <div className="h-full px-8 flex items-center justify-between">
        {/* Left: Name */}
        <span className="font-bold text-white">Manas Kumar</span>

        {/* Right: Links */}
        <div className="hidden md:flex space-x-6 text-sm text-gray-400">
          <a href="#about" className="hover:text-white">
            About
          </a>
          <a href="#skills" className="hover:text-white">
            Skills
          </a>
          <a href="#projects" className="hover:text-white">
            Projects
          </a>
          <a href="#contact" className="hover:text-white">
            Contact
          </a>
        </div>
      </div>
    </nav>
  );
}
