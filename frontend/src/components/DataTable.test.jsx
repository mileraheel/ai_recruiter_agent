import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataTable from "./DataTable.jsx";

const ROWS = [
  { id: 1, name: "Zebra", count: 3 },
  { id: 2, name: "Acme", count: 10 },
  { id: 3, name: "Mango", count: 1 },
];

const COLUMNS = [
  { key: "name", label: "Name", sortValue: (r) => r.name.toLowerCase(), filterValue: (r) => r.name },
  { key: "count", label: "Count", sortValue: (r) => r.count, filterValue: (r) => r.count },
];

function renderTable(props = {}) {
  return render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} {...props} />);
}

describe("DataTable", () => {
  it("renders every row in its original order with no sort/filter applied", () => {
    renderTable();
    const rows = screen.getAllByRole("row").slice(2); // skip header row + filter row
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining("Zebra"),
      expect.stringContaining("Acme"),
      expect.stringContaining("Mango"),
    ]);
  });

  it("sorts ascending on first header click, descending on second click", async () => {
    const user = userEvent.setup();
    renderTable();

    await user.click(screen.getByRole("button", { name: "Name" }));
    let rows = screen.getAllByRole("row").slice(2);
    expect(rows[0].textContent).toContain("Acme");
    expect(rows[2].textContent).toContain("Zebra");

    await user.click(screen.getByRole("button", { name: /Name/ }));
    rows = screen.getAllByRole("row").slice(2);
    expect(rows[0].textContent).toContain("Zebra");
    expect(rows[2].textContent).toContain("Acme");
  });

  it("sorts numeric columns numerically, not lexicographically", async () => {
    const user = userEvent.setup();
    renderTable();

    await user.click(screen.getByRole("button", { name: "Count" }));
    const rows = screen.getAllByRole("row").slice(2);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining("Mango"), // count 1
      expect.stringContaining("Zebra"), // count 3
      expect.stringContaining("Acme"), // count 10
    ]);
  });

  it("filters rows by a per-column search that only matches that column", async () => {
    const user = userEvent.setup();
    renderTable();

    await user.type(screen.getByLabelText("Filter Name"), "an");

    expect(screen.getByText("Mango")).toBeInTheDocument();
    expect(screen.queryByText("Zebra")).not.toBeInTheDocument();
    expect(screen.queryByText("Acme")).not.toBeInTheDocument();
  });

  it("combines multiple column filters with AND logic", async () => {
    const user = userEvent.setup();
    renderTable();

    await user.type(screen.getByLabelText("Filter Name"), "a");
    await user.type(screen.getByLabelText("Filter Count"), "10");

    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.queryByText("Mango")).not.toBeInTheDocument();
    expect(screen.queryByText("Zebra")).not.toBeInTheDocument();
  });

  it("shows a distinct message when filters match nothing vs. when there's no data at all", async () => {
    const user = userEvent.setup();
    renderTable();

    await user.type(screen.getByLabelText("Filter Name"), "doesnotexist");
    expect(screen.getByText(/no rows match your search/i)).toBeInTheDocument();
  });

  it("shows the custom empty message when there are no rows at all", () => {
    renderTable({ rows: [], emptyMessage: "Nothing here yet." });
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
  });

  it("does not render a search box for a column with no filterValue", () => {
    render(
      <DataTable
        columns={[{ key: "name", label: "Name", sortValue: (r) => r.name }]}
        rows={ROWS}
        rowKey={(r) => r.id}
      />
    );
    expect(screen.queryByLabelText("Filter Name")).not.toBeInTheDocument();
  });

  it("does not make the header clickable for a column with no sortValue", async () => {
    render(
      <DataTable
        columns={[{ key: "name", label: "Name", filterValue: (r) => r.name }]}
        rows={ROWS}
        rowKey={(r) => r.id}
      />
    );
    expect(screen.getByRole("button", { name: "Name" })).toBeDisabled();
  });

  it("supports a custom render function per column, e.g. for action buttons", () => {
    render(
      <DataTable
        columns={[
          { key: "name", label: "Name", sortValue: (r) => r.name },
          { key: "actions", label: "", render: (r) => <button>Delete {r.name}</button> },
        ]}
        rows={ROWS}
        rowKey={(r) => r.id}
      />
    );
    expect(screen.getByRole("button", { name: "Delete Acme" })).toBeInTheDocument();
  });

  it("does not toggle any expanded content when expandedContent is not provided", async () => {
    const user = userEvent.setup();
    renderTable();
    await user.click(screen.getByText("Acme"));
    // Nothing extra should appear -- no expandedContent was given.
    expect(screen.getAllByRole("row")).toHaveLength(5); // 1 header + 1 filter row + 3 data rows
  });

  it("expands and collapses a row's detail content on click when expandedContent is provided", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(r) => r.id}
        expandedContent={(r) => <div>Detail for {r.name}</div>}
      />
    );

    expect(screen.queryByText("Detail for Acme")).not.toBeInTheDocument();

    await user.click(screen.getByText("Acme"));
    expect(screen.getByText("Detail for Acme")).toBeInTheDocument();

    await user.click(screen.getByText("Acme"));
    expect(screen.queryByText("Detail for Acme")).not.toBeInTheDocument();
  });

  it("only expands one row at a time", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(r) => r.id}
        expandedContent={(r) => <div>Detail for {r.name}</div>}
      />
    );

    await user.click(screen.getByText("Acme"));
    expect(screen.getByText("Detail for Acme")).toBeInTheDocument();

    await user.click(screen.getByText("Zebra"));
    expect(screen.getByText("Detail for Zebra")).toBeInTheDocument();
    expect(screen.queryByText("Detail for Acme")).not.toBeInTheDocument();
  });
});
