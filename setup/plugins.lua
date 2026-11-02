local ok, err = pcall(function()
  -- Lazy streams headless output without always recording failed exit codes.
  local task = require("lazy.manage.task")
  local spawn = task.spawn
  task.spawn = function(self, ...)
    local success = spawn(self, ...)
    if not success then self:error("Command failed during plugin restore") end
    return success
  end
  require("lazy").restore({ wait = true, show = false })
  task.spawn = spawn
  for name, plugin in pairs(require("lazy.core.config").plugins) do
    assert(plugin._.installed and not require("lazy.core.plugin").has_errors(plugin),
      "Plugin restore failed: " .. name)
  end
end)
if not ok then
  io.stderr:write(tostring(err) .. "\n")
  vim.cmd("cquit 1")
end
print("Locked plugins restored successfully")
vim.cmd("cquit 0")
