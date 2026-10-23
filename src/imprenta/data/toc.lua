-- Pandoc Lua filter: the positional table of contents.
--
-- The build drops a marker where a product's parts list says `toc` (wrapped,
-- like every part, in its .part div):
--
--   ::: {.toc-marker depth="2" title="Contents" pages="true"}
--   :::
--
-- This filter replaces each marker with a nav listing the headings of
-- everything that comes AFTER it (to `depth`), linking to pandoc's auto ids.
-- Headings before the marker (the cover, a foreword placed ahead of the toc)
-- are not listed. Page numbers are added by CSS (Paged.js target-counter),
-- so the same HTML works for the EPUB, where there are no pages.
--
-- Content is never changed: this filter only adds the nav.

local function collect(blocks, from, depth)
  local items = {}
  local function add(h)
    if h.level <= depth and not h.classes:includes("unlisted") then
      items[#items + 1] = {level = h.level, id = h.identifier,
                           text = pandoc.utils.stringify(h.content)}
    end
  end
  local function visit(b)
    if b.t == "Header" then
      add(b)                       -- walk() only visits children, so test the block itself
    elseif b.t == "Div" then
      if not b.classes:includes("unlisted") then   -- a part with `toc: false` (e.g. a cover)
        for _, child in ipairs(b.content) do visit(child) end
      end
    else
      b:walk({Header = add})
    end
  end
  for i = from, #blocks do visit(blocks[i]) end
  return items
end


-- The marker sits inside its part's wrapper div: find it one level down too.
local function marker_in(b)
  if b.t ~= "Div" then return nil end
  if b.classes:includes("toc-marker") then return b end
  for _, child in ipairs(b.content) do
    if child.t == "Div" and child.classes:includes("toc-marker") then return child end
  end
  return nil
end

local function escape(s)
  return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
end

local function render(items, title, pages)
  local out = {'<nav class="toc' .. (pages and " toc-pages" or "") .. '">'}
  if title and title ~= "" then
    out[#out + 1] = '<h1 class="toc-title">' .. escape(title) .. "</h1>"
  end
  local level = 0
  for _, it in ipairs(items) do
    while level < it.level do
      out[#out + 1] = '<ol class="toc-l' .. (level + 1) .. '">'
      level = level + 1
    end
    while level > it.level do
      out[#out + 1] = "</ol>"
      level = level - 1
    end
    out[#out + 1] = string.format(
      '<li><a href="#%s"><span class="toc-text">%s</span><span class="toc-leader"></span></a></li>',
      it.id, escape(it.text))
  end
  while level > 0 do
    out[#out + 1] = "</ol>"
    level = level - 1
  end
  out[#out + 1] = "</nav>"
  return table.concat(out, "\n")
end

function Pandoc(doc)
  local blocks = doc.blocks
  for i = 1, #blocks do
    local m = marker_in(blocks[i])
    if m then
      local depth = tonumber(m.attributes["depth"]) or 2
      local pages = (m.attributes["pages"] or "true") ~= "false"
      local items = collect(blocks, i + 1, depth)
      blocks[i] = pandoc.RawBlock("html", render(items, m.attributes["title"], pages))
    end
  end
  return doc
end
