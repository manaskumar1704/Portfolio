"use client";

import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Github, ExternalLink } from "lucide-react";
import { motion } from "framer-motion";

interface ProjectProps {
    title: string;
    description: string;
    tags: string[];
    repoLink?: string;
    demoLink?: string;
}

export default function ProjectCard({ title, description, tags, repoLink, demoLink }: ProjectProps) {
    return (
        <motion.div
            whileHover={{ y: -5 }}
            transition={{ duration: 0.3 }}
        >
            <Card className="glass-card h-full flex flex-col overflow-hidden border-border/50">
                <CardHeader>
                    <CardTitle className="text-xl">{title}</CardTitle>
                    <CardDescription className="line-clamp-2 mt-2">
                        {description}
                    </CardDescription>
                </CardHeader>
                <CardContent className="flex-grow">
                    <div className="flex flex-wrap gap-2">
                        {tags.map((tag) => (
                            <Badge key={tag} variant="secondary" className="bg-secondary/50 hover:bg-secondary/70">
                                {tag}
                            </Badge>
                        ))}
                    </div>
                </CardContent>
                <CardFooter className="flex gap-4 pt-4">
                    {repoLink && (
                        <Button variant="outline" size="sm" asChild className="gap-2">
                            <a href={repoLink} target="_blank" rel="noopener noreferrer">
                                <Github size={16} /> Code
                            </a>
                        </Button>
                    )}
                    {demoLink && (
                        <Button size="sm" asChild className="gap-2">
                            <a href={demoLink} target="_blank" rel="noopener noreferrer">
                                <ExternalLink size={16} /> Launch App
                            </a>
                        </Button>
                    )}
                </CardFooter>
            </Card>
        </motion.div>
    );
}
