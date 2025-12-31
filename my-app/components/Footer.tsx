import { Github, Linkedin, Mail } from "lucide-react";

export default function Footer() {
    return (
        <footer className="border-t border-border/40 bg-background/50 backdrop-blur-sm py-12 mt-20">
            <div className="container mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
                <div className="text-center md:text-left">
                    <h3 className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-purple-400">
                        Manas Kumar
                    </h3>
                    <p className="text-sm text-muted-foreground mt-2">
                        Building digital experiences that matter.
                    </p>
                </div>

                <div className="flex items-center gap-6">
                    <a
                        href="https://github.com/manaskumar1704"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <Github size={20} />
                    </a>
                    <a
                        href="https://linkedin.com/in/manas-kumar-372193322"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <Linkedin size={20} />
                    </a>
                    <a
                        href="mailto:manaskumar1704@gmail.com"
                        className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <Mail size={20} />
                    </a>
                </div>

                <div className="text-sm text-muted-foreground">
                    © {new Date().getFullYear()} Manas Kumar. All rights reserved.
                </div>
            </div>
        </footer>
    );
}
