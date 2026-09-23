-- ============================================================
--  init.lua — minimal, fast nvim config
--  Plugins: lazy.nvim · nvim-tree · telescope · gitsigns ·
--           fugitive · lspconfig (gopls) · nvim-cmp · treesitter
-- ============================================================

-- ── Core options ────────────────────────────────────────────
vim.g.mapleader = " "
vim.g.maplocalleader = " "

local o = vim.opt
o.number         = true          -- line numbers
o.relativenumber = true          -- relative line numbers (great for jumps)
o.signcolumn     = "yes"         -- always show sign column (no layout shift)
o.cursorline     = true          -- highlight current line
o.scrolloff      = 8             -- keep 8 lines above/below cursor
o.wrap           = false         -- no line wrapping
o.tabstop        = 4
o.shiftwidth     = 4
o.expandtab      = true
o.smartindent    = true
o.splitright     = true          -- new splits open to the right
o.splitbelow     = true
o.ignorecase     = true          -- case-insensitive search...
o.smartcase      = true          -- ...unless you type a capital
o.updatetime     = 250           -- faster CursorHold / gitsigns updates
o.termguicolors  = true
o.clipboard      = "unnamedplus" -- use system clipboard
o.undofile       = true          -- persist undo history across sessions

-- ── Bootstrap lazy.nvim ─────────────────────────────────────
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    "git", "clone", "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

-- ── Plugins ─────────────────────────────────────────────────
require("lazy").setup({

  -- Theme
  {
    "folke/tokyonight.nvim",
    priority = 1000,
    config = function()
      require("tokyonight").setup({ style = "night" })
      vim.cmd.colorscheme("tokyonight-night")
    end,
  },

  -- File tree
  {
    "nvim-tree/nvim-tree.lua",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("nvim-tree").setup({
        view = { width = 35 },
        renderer = { group_empty = true },
        filters = { dotfiles = false },
      })
    end,
  },

  -- Fuzzy finder
  {
    "nvim-telescope/telescope.nvim",
    branch = "0.1.x",
    dependencies = { "nvim-lua/plenary.nvim" },
    config = function()
      require("telescope").setup({
        defaults = {
          file_ignore_patterns = { "%.git/", "node_modules" },
          preview = {
            treesitter = false,
          },
        },
      })
    end,
  },

  -- Git signs (inline blame, hunk preview)
  {
    "lewis6991/gitsigns.nvim",
    config = function()
      require("gitsigns").setup({
        signs = {
          add    = { text = "▎" },
          change = { text = "▎" },
          delete = { text = "󰍵" },
        },
        current_line_blame = true,
        current_line_blame_opts = { delay = 500 },
      })
    end,
  },

  -- Git commands (:Git ...)
  "tpope/vim-fugitive",

  -- Mason (just for installing gopls binary)
  {
    "williamboman/mason.nvim",
    config = function()
      require("mason").setup()
      -- Auto-install gopls if missing
      local mr = require("mason-registry")
      if not mr.is_installed("gopls") then
        vim.cmd("MasonInstall gopls")
      end
    end,
  },

  -- Autocompletion (keep as-is, just move capabilities setup here)
  {
    "hrsh7th/nvim-cmp",
    dependencies = {
      "hrsh7th/cmp-nvim-lsp",
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "L3MON4D3/LuaSnip",
      "saadparwaiz1/cmp_luasnip",
    },
    config = function()
      -- Native nvim -1.11+ LSP config
      vim.lsp.config("gopls", {
        cmd = { "gopls" },
        filetypes = { "go", "gomod", "gowork", "gotmpl" },
        root_markers = { "go.work", "go.mod", ".git" },
        capabilities = require("cmp_nvim_lsp").default_capabilities(),
        settings = {
          gopls = {
            analyses   = { unusedparams = true },
            staticcheck = true,
            gofumpt    = true,
          },
        },
      })
      vim.lsp.enable("gopls")

      -- LSP keymaps
      vim.api.nvim_create_autocmd("LspAttach", {
        callback = function(ev)
          local map = function(keys, func, desc)
            vim.keymap.set("n", keys, func, { buffer = ev.buf, desc = desc })
          end
          local tb = require("telescope.builtin")
          map("gd",         tb.lsp_definitions,      "Go to definition")
          map("gr",         tb.lsp_references,        "Go to references")
          map("K",          vim.lsp.buf.hover,        "Hover docs")
          map("<leader>rn", vim.lsp.buf.rename,       "Rename symbol")
          map("<leader>ca", vim.lsp.buf.code_action,  "Code action")
          map("<leader>f",  vim.lsp.buf.format,       "Format file")
          map("[d",         vim.diagnostic.goto_prev, "Prev diagnostic")
          map("]d",         vim.diagnostic.goto_next, "Next diagnostic")
        end,
      })

      -- nvim-cmp setup
      local cmp = require("cmp")
      local luasnip = require("luasnip")
      cmp.setup({
        snippet = {
          expand = function(args) luasnip.lsp_expand(args.body) end,
        },
        mapping = cmp.mapping.preset.insert({
          ["<C-Space>"] = cmp.mapping.complete(),
          ["<CR>"]      = cmp.mapping.confirm({ select = true }),
          ["<Tab>"]     = cmp.mapping(function(fallback)
            if cmp.visible() then cmp.select_next_item()
            elseif luasnip.expand_or_jumpable() then luasnip.expand_or_jump()
            else fallback() end
          end, { "i", "s" }),
          ["<S-Tab>"]   = cmp.mapping(function(fallback)
            if cmp.visible() then cmp.select_prev_item()
            elseif luasnip.jumpable(-1) then luasnip.jump(-1)
            else fallback() end
          end, { "i", "s" }),
        }),
        sources = cmp.config.sources({
          { name = "nvim_lsp" },
          { name = "luasnip" },
          { name = "buffer" },
          { name = "path" },
        }),
      })
    end,
  },

  -- Treesitter (parser installer — highlighting is built into nvim 0.12+)
  -- Must track the `main` branch: `master` is archived and its API lacks
  -- get_installed()/install(). main does not support lazy-loading.
  -- Pinned to a commit verified working with arm64-rebuilt parsers (see
  -- 57e73d7) so routine lockfile syncs can't drift it and reintroduce
  -- an ABI mismatch; bump deliberately and rebuild parsers when you do.
  {
    "nvim-treesitter/nvim-treesitter",
    branch = "main",
    commit = "c9f9ed6c1892f629ea399f4ee7905f2686fa13f2",
    lazy = false,
    build = ":TSUpdate",
    config = function()
      local ts = require("nvim-treesitter")
      ts.setup()

      local wanted = { "go", "lua", "bash", "markdown", "sql", "python", "json", "yaml" }
      local installed = ts.get_installed()
      local to_install = vim.tbl_filter(function(lang)
        return not vim.tbl_contains(installed, lang)
      end, wanted)
      if #to_install > 0 then
        ts.install(to_install)
      end

      -- main branch ships queries but does not enable any features; highlighting,
      -- folds and indent are opt-in per buffer via Nvim's built-in treesitter.
      vim.api.nvim_create_autocmd("FileType", {
        callback = function(ev)
          local lang = vim.treesitter.language.get_lang(vim.bo[ev.buf].filetype)
          if not lang or not vim.tbl_contains(ts.get_installed(), lang) then
            return
          end
          if not pcall(vim.treesitter.start, ev.buf, lang) then
            return
          end
          vim.wo[0][0].foldexpr = "v:lua.vim.treesitter.foldexpr()"
          vim.bo[ev.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
        end,
      })
    end,
  },

  -- Status line
  {
    "nvim-lualine/lualine.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("lualine").setup({ options = { theme = "tokyonight" } })
    end,
  },

}, {
  -- lazy.nvim options
  ui = { border = "rounded" },
})

-- ── Keymaps ─────────────────────────────────────────────────
local map = function(mode, keys, func, desc)
  vim.keymap.set(mode, keys, func, { desc = desc, silent = true })
end
-- File tree
map("n", "<leader>e", "<cmd>NvimTreeToggle<CR>",   "Toggle file tree")
map("n", "<leader>o", "<cmd>NvimTreeFocus<CR>",    "Focus file tree")

-- Telescope
map("n", "<leader>ff", function() require("telescope.builtin").find_files() end,  "Find files")
map("n", "<leader>fg", function() require("telescope.builtin").live_grep() end,   "Live grep")
map("n", "<leader>fb", function() require("telescope.builtin").buffers() end,     "Buffers")
map("n", "<leader>fh", function() require("telescope.builtin").help_tags() end,   "Help tags")

-- Git (fugitive)
map("n", "<leader>gs", "<cmd>Git<CR>",             "Git status")
map("n", "<leader>gc", "<cmd>Git commit<CR>",      "Git commit")
map("n", "<leader>gp", "<cmd>Git push<CR>",        "Git push")
map("n", "<leader>gl", "<cmd>Git log<CR>",         "Git log")

-- Gitsigns hunk navigation
map("n", "]h", "<cmd>Gitsigns next_hunk<CR>",      "Next hunk")
map("n", "[h", "<cmd>Gitsigns prev_hunk<CR>",      "Prev hunk")
map("n", "<leader>hp", "<cmd>Gitsigns preview_hunk<CR>", "Preview hunk")
map("n", "<leader>hr", "<cmd>Gitsigns reset_hunk<CR>",   "Reset hunk")

-- Window navigation
map("n", "<C-h>", "<C-w>h", "Move to left window")
map("n", "<C-l>", "<C-w>l", "Move to right window")
map("n", "<C-j>", "<C-w>j", "Move to lower window")
map("n", "<C-k>", "<C-w>k", "Move to upper window")

-- Clear search highlight
map("n", "<Esc>", "<cmd>nohlsearch<CR>", "Clear highlight")

-- Insert mode escape
map("i", "jk", "<Esc>", "Exit insert mode")

