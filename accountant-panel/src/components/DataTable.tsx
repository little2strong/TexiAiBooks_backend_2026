import { useMemo, useState, useEffect, useRef, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
} from "@tanstack/react-table";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Input,
  Modal,
  Pagination,
  Select,
  Skeleton,
  Space,
  Tooltip,
} from "antd";
import {
  Download,
  ListFilter,
  RefreshCw,
  Save,
  Rows3,
  FileCheck2,
} from "lucide-react";
import { api, download, request } from "../api/client";
import { tablePath } from "../api/providers";
import type { Page, TableQuery } from "../api/types";
import { RoleGuard } from "./RoleGuard";

export interface TableProps<T> {
  resource: string;
  columns: ColumnDef<T>[];
  query: TableQuery;
  onQuery: (query: TableQuery) => void;
  title: string;
  toolbar?: ReactNode;
  selectable?: boolean;
  selectionAction?: (selected: T[], clear: () => void) => ReactNode;
  onData?: (data: Page<T> & Record<string, unknown>) => void;
}

export function DataTable<T extends { id: string }>({
  resource,
  columns,
  query,
  onQuery,
  title,
  toolbar,
  selectable,
  selectionAction,
  onData,
}: TableProps<T>) {
  const { message } = App.useApp();
  const cache = useQueryClient();
  const [selection, setSelection] = useState<RowSelectionState>({});
  const [search, setSearch] = useState(query.search);
  const [saveOpen, setSaveOpen] = useState(false);
  const [viewName, setViewName] = useState("");
  const [busy, setBusy] = useState(false);
  const [viewBusy, setViewBusy] = useState(false);
  const [compact, setCompact] = useState(false);
  const numeric = (id: string) =>
    /pence|amount|deductible|miles|odometer|percent|confidence|age_days/.test(
      id,
    );
  const previousRows = useRef<{
    scope: string;
    rows: Map<string, { json: string; status: unknown }>;
  } | null>(null);
  const [highlights, setHighlights] = useState<Record<string, string>>({});
  const scope = JSON.stringify([resource, query]);
  const identifierSearch =
    ["drivers", "handoffs"].includes(resource) &&
    /^\d+$/.test(query.search.trim());
  const result = useQuery({
    queryKey: ["table", resource, query],
    queryFn: ({ signal }) =>
      request<Page<T> & Record<string, unknown>>(tablePath(resource), {
        method: "POST",
        body: query,
        signal,
      }),
  });
  const views = useQuery({
    queryKey: ["views", resource],
    queryFn: () => api.views(resource),
    retry: false,
  });
  useEffect(() => {
    if (!result.data) return;
    const rows = new Map(
      result.data.items.map((row) => {
        const workflow = row as T & { review_status?: string; status?: string };
        return [
          row.id,
          {
            json: JSON.stringify(row),
            status: workflow.review_status || workflow.status,
          },
        ] as const;
      }),
    );
    const changed: Record<string, string> = {};
    if (previousRows.current?.scope === scope) {
      rows.forEach((value, id) => {
        const previous = previousRows.current!.rows.get(id);
        if (previous?.json !== value.json)
          changed[id] =
            previous?.status !== value.status &&
            ["confirmed", "ready_to_file", "filed"].includes(
              String(value.status),
            )
              ? "row-approved"
              : "row-flash";
      });
    }
    previousRows.current = { scope, rows };
    setHighlights(changed);
    if (!Object.keys(changed).length) return;
    const lifetime = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        "--motion-shimmer",
      ),
    );
    const timeout = setTimeout(() => setHighlights({}), lifetime);
    return () => clearTimeout(timeout);
  }, [result.data, scope]);
  useEffect(() => {
    setSelection({});
    setSearch(query.search);
  }, [query, resource]);
  useEffect(() => {
    if (result.data) onData?.(result.data);
  }, [result.data, onData]);
  const tableColumns = useMemo<ColumnDef<T>[]>(
    () =>
      selectable
        ? [
            {
              id: "selection",
              enableSorting: false,
              header: ({ table }) => (
                <Checkbox
                  aria-label="Select all rows on this page"
                  checked={table.getIsAllPageRowsSelected()}
                  indeterminate={table.getIsSomePageRowsSelected()}
                  onChange={(event) =>
                    table.toggleAllPageRowsSelected(event.target.checked)
                  }
                />
              ),
              cell: ({ row }) => (
                <Checkbox
                  aria-label={`Select row ${row.index + 1}`}
                  checked={row.getIsSelected()}
                  onChange={(event) => row.toggleSelected(event.target.checked)}
                />
              ),
            },
            ...columns,
          ]
        : columns,
    [selectable, columns],
  );
  const table = useReactTable({
    data: result.data?.items || [],
    columns: tableColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    rowCount: result.data?.total || 0,
    state: {
      pagination: { pageIndex: query.page - 1, pageSize: query.page_size },
      sorting: [{ id: query.sort, desc: query.order === "desc" }],
      rowSelection: selection,
    },
    onRowSelectionChange: setSelection,
    enableRowSelection: selectable,
  });
  const exportCsv = async () => {
    setBusy(true);
    try {
      const match = resource.match(/^drivers\/([^/]+)\/(.+)$/);
      const blob = await request<Blob>("/staff/exports", {
        method: "POST",
        binary: true,
        body: {
          resource: match ? match[2] : resource,
          driver_id: match?.[1] || null,
          query,
        },
      });
      download(blob, "taxiaibooks-export.csv");
      void message.success("Filtered CSV exported.");
    } catch (error) {
      void message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    if (!viewName.trim()) return;
    setViewBusy(true);
    try {
      await api.saveView(resource, viewName.trim(), query);
      await cache.invalidateQueries({ queryKey: ["views", resource] });
      setSaveOpen(false);
      setViewName("");
    } catch (error) {
      void message.error((error as Error).message);
    } finally {
      setViewBusy(false);
    }
  };
  const selected = table.getSelectedRowModel().rows.map((row) => row.original);
  return (
    <section
      className={`surface data-table ${compact ? "table-compact" : ""}`}
      aria-label={title}
    >
      <div className="table-toolbar">
        <Input.Search
          aria-label={`Search ${title.toLowerCase()}`}
          placeholder="Search records…"
          value={search}
          allowClear
          onChange={(event) => {
            setSearch(event.target.value);
            if (!event.target.value) onQuery({ ...query, page: 1, search: "" });
          }}
          onSearch={(value) => onQuery({ ...query, page: 1, search: value })}
          className="table-search"
        />
        {toolbar}
        <div className="toolbar-spacer" />
        <Tooltip title={compact ? "Comfortable rows" : "Compact rows"}>
          <Button
            aria-label={`Toggle compact rows for ${title.toLowerCase()}`}
            aria-pressed={compact}
            icon={<Rows3 />}
            onClick={() => setCompact((value) => !value)}
          />
        </Tooltip>
        <Select
          aria-label="Saved views"
          placeholder="Saved views"
          className="saved-views"
          value={undefined}
          loading={views.isPending}
          disabled={views.isError}
          suffixIcon={<ListFilter />}
          options={views.data?.items.map((view) => ({
            value: view.id,
            label: view.name,
          }))}
          onSelect={(id) => {
            const view = views.data?.items.find((item) => item.id === id);
            if (view) onQuery(view.query);
          }}
        />
        <Tooltip title="Save the current filters and sort">
          <Button
            aria-label="Save current view"
            icon={<Save />}
            onClick={() => setSaveOpen(true)}
          />
        </Tooltip>
        <RoleGuard action="export">
          <Button
            icon={<Download />}
            onClick={() => void exportCsv()}
            loading={busy}
          >
            Export CSV
          </Button>
        </RoleGuard>
        <Tooltip title="Refresh records">
          <Button
            icon={<RefreshCw />}
            aria-label={`Refresh ${title.toLowerCase()}`}
            onClick={() => void result.refetch()}
          />
        </Tooltip>
      </div>
      {views.isError && (
        <Alert
          className="table-notice"
          type="warning"
          title="Saved views are unavailable"
          action={
            <Button size="small" onClick={() => void views.refetch()}>
              Retry
            </Button>
          }
        />
      )}
      {selected.length > 0 && (
        <div className="selection-bar">
          <strong>{selected.length} selected</strong>
          {selectionAction?.(selected, () => setSelection({}))}
          <Button size="small" onClick={() => setSelection({})}>
            Clear selection
          </Button>
        </div>
      )}
      {result.isError ? (
        <div className="state-padding">
          <Alert
            type="error"
            showIcon
            title="Could not load records"
            description={result.error.message}
            action={
              <Button onClick={() => void result.refetch()}>Retry</Button>
            }
          />
        </div>
      ) : result.isPending ? (
        <div
          className="state-padding"
          aria-label={`Loading ${title.toLowerCase()}`}
        >
          <Skeleton active paragraph={{ rows: 5 }} />
        </div>
      ) : (
        <div
          className="table-scroll"
          tabIndex={0}
          role="region"
          aria-label={`${title}, scroll horizontally for more columns`}
        >
          <table>
            <caption className="sr-only">
              {title}. {result.data.total} records. Page {query.page}.
            </caption>
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {group.headers.map((header) => (
                    <th
                      key={header.id}
                      scope="col"
                      data-numeric={numeric(header.column.id)}
                      aria-sort={
                        header.column.getIsSorted() === "asc"
                          ? "ascending"
                          : header.column.getIsSorted() === "desc"
                            ? "descending"
                            : undefined
                      }
                    >
                      {header.column.getCanSort() ? (
                        <button
                          className="sort-button"
                          onClick={() =>
                            onQuery({
                              ...query,
                              page: 1,
                              sort: header.column.id,
                              order:
                                query.sort === header.column.id &&
                                query.order === "asc"
                                  ? "desc"
                                  : "asc",
                            })
                          }
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          <span aria-hidden="true">
                            {header.column.getIsSorted() === "asc"
                              ? " ↑"
                              : header.column.getIsSorted() === "desc"
                                ? " ↓"
                                : " ↕"}
                          </span>
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={highlights[row.id]}
                  data-selected={row.getIsSelected()}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} data-numeric={numeric(cell.column.id)}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {!result.data.items.length && (
            <div className="empty-state">
              <FileCheck2 aria-hidden="true" />
              <p>No records match this view.</p>
              <Button
                type="primary"
                onClick={() => {
                  if (query.search || Object.keys(query.filters).length)
                    onQuery({ ...query, page: 1, search: "", filters: {} });
                  else void result.refetch();
                }}
              >
                {query.search || Object.keys(query.filters).length
                  ? "Clear filters"
                  : "Refresh records"}
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="table-footer">
        <span aria-live="polite">
          {result.data?.total?.toLocaleString() ?? "—"} records · filtered
          results
        </span>
        <Pagination
          size="small"
          current={query.page}
          pageSize={query.page_size}
          total={result.data?.total || 0}
          showSizeChanger
          pageSizeOptions={[10, 25, 50, 100]}
          disabled={result.isPending || result.isError}
          onChange={(page, page_size) =>
            onQuery({
              ...query,
              page: page_size !== query.page_size ? 1 : page,
              page_size,
            })
          }
        />
      </div>
      <Modal
        title="Save this view"
        open={saveOpen}
        onCancel={() => setSaveOpen(false)}
        onOk={() => void save()}
        confirmLoading={viewBusy}
        okButtonProps={{ disabled: !viewName.trim() || identifierSearch }}
      >
        <label htmlFor="saved-view-name">View name</label>
        <Input
          id="saved-view-name"
          value={viewName}
          maxLength={100}
          onChange={(event) => setViewName(event.target.value)}
        />
        <p className="muted">
          Filters, search and sort are saved privately to your staff account.
        </p>
        {identifierSearch && (
          <Alert
            type="info"
            title="UTR searches are never saved"
            description="Clear the identifier search before saving this view."
            className="form-alert"
          />
        )}
        {views.data?.items.length ? (
          <Space orientation="vertical" className="full-width">
            {views.data.items.map((view) => (
              <div key={view.id} className="saved-view-row">
                <span>{view.name}</span>
                <Button
                  danger
                  size="small"
                  onClick={async () => {
                    try {
                      await api.deleteView(view.id);
                      await views.refetch();
                    } catch (error) {
                      void message.error((error as Error).message);
                    }
                  }}
                >
                  Delete
                </Button>
              </div>
            ))}
          </Space>
        ) : null}
      </Modal>
    </section>
  );
}
