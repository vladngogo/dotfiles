local wanted = { "go", "lua", "bash", "markdown", "sql", "python", "json", "yaml" }
local ok, err = pcall(function()
  local ts = require("nvim-treesitter")
  assert(ts.install(wanted):wait(300000), "Parser installation failed")
  assert(ts.update(wanted):wait(300000), "Parser update failed")
  for _, lang in ipairs(wanted) do
    local loaded, result = pcall(vim.treesitter.language.add, lang)
    if not loaded or not result then
      -- An existing parser can have the right revision but the wrong CPU/ABI.
      assert(ts.install({ lang }, { force = true }):wait(300000), "Parser rebuild failed: " .. lang)
    end
    assert(vim.treesitter.language.add(lang), "Parser failed to load: " .. lang)
  end
end)
if not ok then
  io.stderr:write(tostring(err) .. "\n")
  vim.cmd("cquit 1")
end
print("All eight Treesitter parsers installed and loadable")
vim.cmd("qa")
