"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ExternalLink } from "lucide-react";
import { motion } from "framer-motion";

interface SiteProps {
    name: string;
    url: string;
    category: string;
    description: string;
}

export default function SiteCard({ name, url, category, description }: SiteProps) {
    return (
        <motion.a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="block h-full"
        >
            <Card className="glass-card h-full hover:border-primary/50 transition-colors cursor-pointer group">
                <CardHeader>
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-xs text-primary font-mono mb-1 uppercase tracking-wider">{category}</p>
                            <CardTitle className="group-hover:text-primary transition-colors flex items-center gap-2">
                                {name}
                                <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                            </CardTitle>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-muted-foreground">
                        {description}
                    </p>
                </CardContent>
            </Card>
        </motion.a>
    );
}
