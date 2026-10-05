import { allPaths } from "@/lib/api/fs";
import { FsView } from "@/features/fs/fs-view";

/**
 * Prerender every valid path at build time, so shared links, refresh and Back
 * all serve static HTML.
 *
 * `dynamicParams` is deliberately left at its default. A path not in the tree
 * still renders (HTTP 200) and shows the bash error, which is the whole point
 * of the filesystem metaphor rather than a generic 404 page.
 */
export function generateStaticParams() {
  return allPaths().map((path) => ({ path: path.split("/").filter(Boolean) }));
}

export default async function Page({ params }: PageProps<"/[...path]">) {
  const { path } = await params;
  return <FsView path={`/${path.join("/")}`} />;
}