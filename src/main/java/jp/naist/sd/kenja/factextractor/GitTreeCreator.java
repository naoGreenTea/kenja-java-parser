package jp.naist.sd.kenja.factextractor;

import java.io.File;
import java.io.IOException;

import jp.naist.sd.kenja.factextractor.ast.ASTCompilation;

import org.apache.commons.io.IOUtils;
import org.apache.commons.lang3.StringUtils;
import org.eclipse.core.runtime.NullProgressMonitor;
import org.eclipse.jdt.core.dom.AST;
import org.eclipse.jdt.core.dom.ASTParser;
import org.eclipse.jdt.core.dom.CompilationUnit;
import org.eclipse.jgit.lib.ObjectId;
import org.eclipse.jgit.lib.ObjectLoader;
import org.eclipse.jgit.lib.Repository;
import org.eclipse.jgit.storage.file.FileRepository;

import com.google.common.base.Charsets;
import com.google.common.io.Files;

public class GitTreeCreator {
	private Tree root = new Tree("");

	private ASTCompilation compilation;

	public GitTreeCreator() {
	}

	private void parseSourcecode(char[] src) {
		ASTParser parser = ASTParser.newParser(AST.JLS4);

		parser.setSource(src);

		NullProgressMonitor nullMonitor = new NullProgressMonitor();
		CompilationUnit unit = (CompilationUnit) parser.createAST(nullMonitor);

		compilation = new ASTCompilation(unit, root);
	}

	public void writeASTAsFileTree(File outputDir) {
		try {
			TreeWriter writer = new TextFormatTreeWriter(outputDir);
			writer.writeTree(compilation.getTree());
		} catch (IOException e) {
			e.printStackTrace();
		}
		// compilation.getTree().writeTree(outputDir);
	}

	public static void main(String[] args) {
		if (args.length != 2) {
			System.out.println("please input output dir and orginal repository path.");
			return;
		}

		try {
			File repoDir = new File(args[1]);
			Repository repo = new FileRepository(repoDir);

			for (String line : IOUtils.readLines(System.in)) {
				line = StringUtils.strip(line);
				File outputDir = new File(args[0], line);
				ObjectId obj = ObjectId.fromString(line);
				ObjectLoader loader = repo.open(obj);
				GitTreeCreator creator = new GitTreeCreator();

				creator.parseSourcecode(IOUtils.toCharArray(loader.openStream()));
				creator.writeASTAsFileTree(outputDir);
			}

		} catch (IOException e) {
			e.printStackTrace();
		}
	}
}
