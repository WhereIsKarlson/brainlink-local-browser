#!/usr/bin/env python3
"""
BrainLink — standalone Python desktop search app (Tkinter).
- Uses duckduckgo-search (free).
- Optionally refines queries with local Ollama (if installed).
- Click results to open them in your system browser.

Usage:
    python brainlink_desktop.py
"""

import subprocess
import sys
import threading
from tkinter import (
    Tk, Frame, Label, Entry, Button, Listbox, Scrollbar,
    StringVar, END, SINGLE, Toplevel, Text, BOTH, RIGHT, Y, LEFT
)
from ddgs import DDGS

APP_TITLE = "BrainLink Browser — Local Search"
DEFAULT_MAX_RESULTS = 8


def try_refine_with_ollama(query: str) -> str:
    """
    Attempt to refine the user's query with Ollama local LLM (llama3).
    If Ollama isn't available or something fails, return the original query.
    """
    prompt = f"Reword this for a web search (concise): {query}"
    try:
        # Simple CLI call: ollama run llama3 "..."
        # Ollama usually prints the model response to stdout.
        # This is intentionally simple and tolerant — if it fails, we fallback.
        cmd = ["ollama", "run", "llama3", prompt]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        out = proc.stdout.strip()
        if out:
            # Some versions of Ollama print metadata — take the last non-empty line.
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            if lines:
                candidate = lines[-1]
                # Very small sanity checks: avoid returning something too long or equal to prompt
                if 3 <= len(candidate) <= 400 and candidate.lower() != prompt.lower():
                    return candidate
        return query
    except Exception:
        return query


def ddg_search(query: str, max_results: int = DEFAULT_MAX_RESULTS):
    """
    Use duckduckgo-search to fetch results. Returns a list of dicts
    with keys: 'title', 'href', 'body'.
    """
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, region="wt-wt", safesearch="Off", timelimit="y", max_results=max_results):
                # r usually contains 'title', 'href', 'body'
                results.append({
                    "title": r.get("title") or r.get("text") or "(no title)",
                    "href": r.get("href") or r.get("url") or "",
                    "body": r.get("body") or ""
                })
    except Exception as e:
        print("DuckDuckGo search failed:", e, file=sys.stderr)
    return results


class BrainLinkGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x650")
        self.root.resizable(True, True)

        # Top area: label + search entry + button
        top = Frame(root, pady=12)
        top.pack(fill="x")

        Label(top, text="BrainLink", font=("Segoe UI", 20, "bold")).pack()

        entry_frame = Frame(root, pady=8)
        entry_frame.pack(fill="x")

        self.query_var = StringVar()
        self.search_entry = Entry(entry_frame, textvariable=self.query_var, font=("Segoe UI", 14))
        self.search_entry.pack(side=LEFT, padx=(12, 6), fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda ev: self.on_search_click())

        self.search_btn = Button(entry_frame, text="Search", font=("Segoe UI", 12, "bold"), command=self.on_search_click)
        self.search_btn.pack(side=LEFT, padx=(6, 12))

        # Status label
        self.status_label = Label(root, text="Type something and hit Search. (Ollama optional)", anchor="w")
        self.status_label.pack(fill="x", padx=12)

        # Results area (listbox + scrollbar)
        results_frame = Frame(root, pady=10)
        results_frame.pack(fill="both", expand=True)

        self.scrollbar = Scrollbar(results_frame)
        self.scrollbar.pack(side=RIGHT, fill=Y)

        self.results_list = Listbox(results_frame, font=("Segoe UI", 12), activestyle="dotbox",
                                   yscrollcommand=self.scrollbar.set, selectmode=SINGLE)
        self.results_list.pack(fill=BOTH, expand=True, padx=12)
        self.results_list.bind("<Double-Button-1>", lambda ev: self.on_result_open())
        self.results_list.bind("<Return>", lambda ev: self.on_result_open())

        self.scrollbar.config(command=self.results_list.yview)

        # Footer buttons
        footer = Frame(root, pady=8)
        footer.pack(fill="x")
        Button(footer, text="Open Link", command=self.on_result_open).pack(side=LEFT, padx=8)
        Button(footer, text="Show Snippet", command=self.on_show_snippet).pack(side=LEFT)
        Button(footer, text="Clear", command=self.clear_results).pack(side=LEFT, padx=8)
        Button(footer, text="Quit", command=root.quit).pack(side="right", padx=12)

        # store results in a list for click handling
        self.current_results = []

    def set_status(self, text: str):
        self.status_label.config(text=text)
        self.root.update_idletasks()

    def clear_results(self):
        self.results_list.delete(0, END)
        self.current_results = []
        self.set_status("Cleared results.")

    def on_search_click(self):
        raw_query = self.query_var.get().strip()
        if not raw_query:
            self.set_status("Type a query first.")
            return

        # 🧠 NEW: Direct URL detection (so DuckDuckGo doesn’t “paraphrase”)
        if raw_query.startswith(("http://", "https://")):
            url = raw_query
        elif "." in raw_query and " " not in raw_query:
            # Looks like a domain, so assume it’s a site
            url = "http://" + raw_query
        else:
            url = None

        if url:
            self.set_status(f"Opening {url} directly inside BrainLink...")
            try:
                import webview
                webview.create_window("BrainLink Viewer", url)
                webview.start()
            except Exception as e:
                self.set_status(f"Failed to open URL: {e}")
            return

        # 🧩 Otherwise, run a normal search
        self.search_btn.config(state="disabled")
        self.set_status("Refining query (local AI if available)...")

        def worker():
            try:
                refined = try_refine_with_ollama(raw_query)
                if refined != raw_query:
                    self.set_status(f"Refined query: {refined} — searching...")
                else:
                    self.set_status("Searching...")

                results = ddg_search(refined, max_results=DEFAULT_MAX_RESULTS)
                self.root.after(0, lambda: self.display_results(results, refined))
            finally:
                self.root.after(0, lambda: self.search_btn.config(state="normal"))

        import threading
        threading.Thread(target=worker, daemon=True).start()



    def display_results(self, results, used_query):
        self.clear_results()
        if not results:
            self.set_status(f"No results for \"{used_query}\".")
            return

        self.current_results = results
        for idx, r in enumerate(results):
            title = r.get("title") or "(no title)"
            body = r.get("body") or ""
            display = f"{idx+1}. {title} — {body[:140].strip()}"
            self.results_list.insert(END, display)
        self.set_status(f"Found {len(results)} results for \"{used_query}\". Double-click an item to open it.")

    class BrainLinkGUI:
        def __init__(self, root):
            ...
    
    def on_result_open(self):   # 👈 notice it's inside the class
        sel = self.results_list.curselection()
        if not sel:
            self.set_status("No result selected.")
            return
        idx = sel[0]
        target = self.current_results[idx].get("href")
        if not target:
            self.set_status("Result has no link.")
            return

        import webview
        self.set_status(f"Opening {target} inside BrainLink...")
        webview.create_window("BrainLink Viewer", target)
        webview.start()

    def on_show_snippet(self):
        sel = self.results_list.curselection()
        if not sel:
            self.set_status("No result selected.")
            return
        idx = sel[0]
        r = self.current_results[idx]
        title = r.get("title", "(no title)")
        body = r.get("body", "(no snippet)")
        href = r.get("href", "(no link)")

        popup = Toplevel(self.root)
        popup.title("Snippet — " + (title[:40] if title else "Snippet"))
        popup.geometry("700x400")
        text_widget = Text(popup, wrap="word")
        text_widget.pack(fill=BOTH, expand=True)
        text_widget.insert("1.0", f"Title: {title}\n\nURL: {href}\n\nSnippet:\n{body}")
        text_widget.config(state="disabled")


def main():
    root = Tk()
    app = BrainLinkGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
