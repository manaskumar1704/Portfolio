export default function Navbar() {
    return (
        <nav className="fixed top-0 left-0 w-full bg-black border-b border-zinc-800 px-8 py-4 z-40">
            <div className="flex justify-between items-center">
                <span className="font-bold text-white">Manas Kumar</span>
                <div className="space-x-6 text-sm text-gray-400">
                    <a href="#about" className="hover:text-white">About</a>
                    <a href="#projects" className="hover:text-white">Projects</a>
                    <a href="#skills" className="hover:text-white">Skills</a>
                </div> 
            </div>
        </nav>
    );
}