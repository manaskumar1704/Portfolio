type SectionProps = {
    id: string;
    title: string;
    children: React.ReactNode;
};

export default function Section({ id, title, children}: SectionProps){
    return (
        <section id={id} className="mt-12 max-w-3xl">
            <h2 className="text-2xl font-semibold">{ title }</h2>
            <div className="mt-4 text-gray-400">
                { children }
            </div>
        </section>
    )
}