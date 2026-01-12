import fs from "fs/promises";
import path from "path";
import { YamlImportForm } from "./YamlImportForm";

function formatName(filename: string): string {
    return filename
        .replace(/^\d+_/, '') // Remove leading numbers like "01_"
        .replace(/\.yaml$/, '') // Remove extension
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

export default async function ImportYamlPage() {
    // Read the documentation file
    const guidePath = path.join(process.cwd(), "public", "docs", "ML_SCENARIO_YAML_GUIDE.md");
    let guideContent = "";
    try {
        guideContent = await fs.readFile(guidePath, "utf-8");
    } catch (e) {
        console.error("Failed to read guide file", e);
        guideContent = "Documentation not found.";
    }

    // Read sample files from public/samples directory
    const samplesDir = path.join(process.cwd(), "public", "samples");
    const templates = [];

    try {
        const files = await fs.readdir(samplesDir);

        for (const file of files) {
            if (file.endsWith(".yaml")) {
                try {
                    const content = await fs.readFile(path.join(samplesDir, file), "utf-8");
                    templates.push({
                        name: formatName(file),
                        filename: file,
                        content: content
                    });
                } catch (err) {
                    console.error(`Failed to read template ${file}`, err);
                }
            }
        }
    } catch (e) {
        console.error("Failed to read samples directory", e);
        // Fallback or empty list
    }

    // Sort templates alphabetically by filename to keep order (01, 02, etc)
    templates.sort((a, b) => a.filename.localeCompare(b.filename));

    return (
        <YamlImportForm
            guideContent={guideContent}
            templates={templates}
        />
    );
}
