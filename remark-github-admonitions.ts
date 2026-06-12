/**
 * Remark plugin to convert GitHub-style admonitions (e.g. [!NOTE]) into container directives.
 * Allows use of GitHub's admonition syntax while still rendering them as proper admonitions in Docusaurus.
 */


import { visit } from 'unist-util-visit';
import type { Plugin } from 'unified';

const admonitionMap: Record<string, string> = {
  NOTE: 'note',
  TIP: 'tip',
  IMPORTANT: 'warning[Important]',
  WARNING: 'warning',
  CAUTION: 'danger',
};

const remarkGithubAdmonitions: Plugin = () => (tree) => {
  visit(tree, 'blockquote', (node: any, index, parent) => {
    const firstParagraph = node.children?.[0];
    const firstText = firstParagraph?.children?.[0];
    if (firstText?.type !== 'text') return;

    const match = firstText.value.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/);
    if (!match) return;

    const type = match[1];
    firstText.value = firstText.value.slice(match[0].length);

    const nameMap: Record<string, string> = {
      NOTE: 'note',
      TIP: 'tip',
      IMPORTANT: 'warning',
      WARNING: 'warning',
      CAUTION: 'danger',
    };

    const labelMap: Record<string, string> = {
      IMPORTANT: 'Important',
    };
    
    if (index === undefined || !parent) return;
    parent.children[index] = {
      type: 'containerDirective',
      name: nameMap[type],
      attributes: labelMap[type] ? { label: labelMap[type] } : {},
      children: node.children,
      data: { 
            hName: 'admonition',
            hProperties: {
              type: nameMap[type],
                ...(labelMap[type] ? { title: labelMap[type] } : {}),
            }
        }
    };
  });
};

export default remarkGithubAdmonitions;