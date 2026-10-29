import { forwardRef, useEffect, useRef, useState } from 'react';
import { DollarSign, Download, Package, Plus, Printer, Receipt, Trash2, TrendingUp, Wallet, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useReactToPrint } from 'react-to-print';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import { useGetInventoryItemsQuery, useGetStoreSettingsQuery } from '@/store/api/productsApi';
import {
  useCreateExpenseMutation,
  useDeleteExpenseMutation,
  useGetExpensesByProductQuery,
  useGetExpensesQuery,
  useGetFinanceSummaryQuery,
  useGetIncomeQuery,
  useGetProductFinanceQuery,
  useUpdateExpenseMutation,
} from '@/store/api/paymentsApi';

const CATEGORIES = [
  { value: 'shipping', label: 'Shipping & Delivery' },
  { value: 'marketing', label: 'Marketing & Ads' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'rent', label: 'Rent' },
  { value: 'salaries', label: 'Salaries' },
  { value: 'packaging', label: 'Packaging' },
  { value: 'software', label: 'Software & Tools' },
  { value: 'miscellaneous', label: 'Miscellaneous' },
];

const METHODS = [
  { value: '', label: 'Not specified' },
  { value: 'cash', label: 'Cash' },
  { value: 'card', label: 'Card' },
  { value: 'mobile_banking', label: 'Mobile Banking' },
];

const emptyForm = {
  expense_date: new Date().toISOString().split('T')[0],
  category: 'shipping',
  description: '',
  amount: '',
  payment_method: '',
  payee: '',
  product: '',
};

function money(value) {
  if (value == null) return '—';
  return `৳${Number(value || 0).toLocaleString()}`;
}

function errorText(error) {
  const data = error?.data;
  if (!data) return 'Could not save the expense';
  if (typeof data.detail === 'string') return data.detail;
  const first = Object.values(data)[0];
  if (Array.isArray(first)) return first[0];
  if (first && typeof first === 'object') return Object.values(first)[0];
  return 'Could not save the expense';
}

function rowsOf(data) {
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

export default function FinancePage() {
  const [dateRange, setDateRange] = useState({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
  });
  const [tab, setTab] = useState('income');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [selected, setSelected] = useState(null);
  const [voucher, setVoucher] = useState(null);
  const [shouldPrint, setShouldPrint] = useState(false);
  const printRef = useRef(null);

  const { data: income, isLoading: incomeLoading, isError: incomeError, refetch: refetchIncome } = useGetIncomeQuery(dateRange);
  const { data: expensesData, isLoading: expensesLoading, isError: expensesError, refetch: refetchExpenses } = useGetExpensesQuery(dateRange);
  const { data: byProduct = [], isLoading: byProductLoading } = useGetExpensesByProductQuery(dateRange);
  const { data: summary, isLoading: summaryLoading, isError: summaryError, refetch: refetchSummary } = useGetFinanceSummaryQuery();
  const { data: productFinance = [], isLoading: productFinanceLoading, isError: productFinanceError, refetch: refetchProductFinance } = useGetProductFinanceQuery();
  const { data: settings } = useGetStoreSettingsQuery();
  const { data: inventory } = useGetInventoryItemsQuery({}, { skip: !formOpen });
  const [createExpense, { isLoading: creating }] = useCreateExpenseMutation();
  const [updateExpense, { isLoading: updating }] = useUpdateExpenseMutation();
  const [deleteExpense] = useDeleteExpenseMutation();

  const expenses = rowsOf(expensesData);
  const products = inventory?.items || [];
  const saving = creating || updating;
  const purchaseLocked = Boolean(editing?.is_purchase_voucher);
  const categoryOptions = editing?.category === 'inventory_purchase'
    ? [{ value: 'inventory_purchase', label: 'Inventory Purchase' }, ...CATEGORIES]
    : CATEGORIES;

  const handlePrint = useReactToPrint({ content: () => printRef.current });

  useEffect(() => {
    if (shouldPrint && voucher) {
      handlePrint();
      setShouldPrint(false);
    }
  }, [shouldPrint, voucher, handlePrint]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEdit = (expense) => {
    setEditing(expense);
    setForm({
      expense_date: expense.expense_date,
      category: expense.category,
      description: expense.description,
      amount: expense.amount,
      payment_method: expense.payment_method || '',
      payee: expense.payee || '',
      product: expense.product || '',
    });
    setFormOpen(true);
  };

  const printVoucher = (expense) => {
    setVoucher(expense);
    setShouldPrint(true);
  };

  const saveExpense = async (event) => {
    event.preventDefault();
    const payload = {
      ...form,
      amount: form.amount,
      product: form.product || null,
      payment_method: form.payment_method || '',
    };
    try {
      if (editing) {
        await updateExpense({ id: editing.id, ...payload }).unwrap();
        toast.success('Expense updated');
      } else {
        const created = await createExpense(payload).unwrap();
        toast.success(`Expense ${created.voucher_number} recorded`);
      }
      setFormOpen(false);
    } catch (error) {
      toast.error(errorText(error));
    }
  };

  const removeExpense = async (expense) => {
    if (!confirm(`Delete voucher ${expense.voucher_number}?`)) return;
    try {
      await deleteExpense(expense.id).unwrap();
      if (selected?.id === expense.id) setSelected(null);
      toast.success('Expense deleted');
    } catch (error) {
      toast.error(errorText(error));
    }
  };

  return (
    <AdminLayout title="Finance">
      <div className="flex flex-col gap-4 mb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Finance</h1>
          <p className="text-sm text-gray-500">
            Actual figures come from completed sales and recorded costs. Estimates value stock that is still on hand at current selling prices. The dates below filter the income and expense lists only.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={dateRange.start_date}
            onChange={(event) => setDateRange({ ...dateRange, start_date: event.target.value })}
            className="input w-auto"
            aria-label="From date"
          />
          <span className="text-sm text-gray-400">to</span>
          <input
            type="date"
            value={dateRange.end_date}
            onChange={(event) => setDateRange({ ...dateRange, end_date: event.target.value })}
            className="input w-auto"
            aria-label="To date"
          />
        </div>
      </div>

      {summaryError ? (
        <LoadError title="Could not load the finance summary" onRetry={refetchSummary} />
      ) : (
        <div className="space-y-6 mb-6">
          <section>
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-gray-900">Actual results</h2>
              <p className="text-sm text-gray-500">Completed sales, purchase costs, and other recorded expenses. This is the current position for all dates.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <Summary icon={DollarSign} label="Current revenue" value={summaryLoading ? '…' : money(summary?.actual?.current_revenue)} tone="green" hint="Merchandise on completed sales" />
              <Summary icon={Package} label="Cost of goods sold" value={summaryLoading ? '…' : money(summary?.actual?.cost_of_goods_sold)} tone="red" hint="Cost of units already sold" />
              <Summary icon={Wallet} label="Realized gross profit" value={summaryLoading ? '…' : money(summary?.actual?.realized_gross_profit)} tone="blue" hint="Current revenue minus cost of goods sold" />
              <Summary icon={Receipt} label="Total product purchase cost" value={summaryLoading ? '…' : money(summary?.actual?.total_product_purchase_cost)} tone="purple" hint="Purchase vouchers plus opening stock" />
              <Summary icon={Receipt} label="Additional expenses" value={summaryLoading ? '…' : money(summary?.actual?.additional_expenses)} tone="red" hint="Delivery, packaging, marketing, and other costs" />
              <Summary icon={Download} label="Inventory losses" value={summaryLoading ? '…' : money(summary?.actual?.inventory_losses)} tone="purple" hint="Damage, loss, and other non-sale reductions" />
              <Summary icon={DollarSign} label="Delivery collected" value={summaryLoading ? '…' : money(summary?.actual?.delivery_collected)} tone="green" hint="On completed sales, separate from product revenue" />
              <Summary icon={Download} label="Order discounts" value={summaryLoading ? '…' : money(summary?.actual?.order_discounts)} tone="purple" hint="On completed sales, separate from product revenue" />
            </div>
            {!summaryLoading && Number(summary?.actual?.opening_stock_cost) > 0 && (
              <p className="text-xs text-gray-500 mt-2">
                Opening stock cost {money(summary.actual.opening_stock_cost)} is included in total product purchase cost. {summary.actual.opening_stock_note} Purchase vouchers are {money(summary.actual.purchase_vouchers_total)}.
              </p>
            )}
          </section>

          <section>
            <div className="mb-3">
              <h2 className="text-lg font-semibold text-gray-900">Estimates</h2>
              <p className="text-sm text-gray-500">{summary?.estimated?.note || 'Unsold stock is not realized revenue or profit.'}</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              <Summary icon={TrendingUp} label="Estimated selling value" value={summaryLoading ? '…' : money(summary?.estimated?.selling_value)} tone="green" hint="Remaining stock at current selling prices" />
              <Summary icon={Wallet} label="Estimated remaining profit" value={summaryLoading ? '…' : money(summary?.estimated?.remaining_gross_profit)} tone="blue" hint="Estimated selling value minus cost still in stock" />
              <Summary icon={Wallet} label="Estimated total profit" value={summaryLoading ? '…' : money(summary?.estimated?.total_profit)} tone="purple" hint="Realized profit plus remaining profit, minus additional expenses and inventory losses" />
            </div>
          </section>

          {!summaryLoading && Number(summary?.awaiting_payment?.quantity) > 0 && (
            <section className="card p-4">
              <h2 className="font-semibold text-gray-900">Awaiting payment</h2>
              <p className="text-sm text-gray-500 mt-1">{summary.awaiting_payment.note}</p>
              <p className="text-sm text-gray-700 mt-2">
                {summary.awaiting_payment.order_count} orders, {summary.awaiting_payment.quantity} units,
                merchandise {money(summary.awaiting_payment.merchandise_total)}, cost {money(summary.awaiting_payment.cost)}.
              </p>
            </section>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-6">
        {[
          ['income', 'Income'],
          ['expenses', 'Expenses'],
          ['profit', 'Product profit'],
          ['products', 'Expenses by product'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === id ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'income' && (
        incomeError ? <LoadError title="Could not load income" onRetry={refetchIncome} /> : (
        <div className="space-y-6">
          <section className="card overflow-hidden">
            <div className="px-4 py-3 border-b">
              <h2 className="font-semibold text-gray-900">Income</h2>
              <p className="text-xs text-gray-500 mt-1">Order payments in the selected dates, including delivery charges. Product profit uses merchandise line totals.</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    {['Date', 'Source', 'Reference', 'Customer', 'Amount'].map((heading) => (
                      <th key={heading} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {incomeLoading ? (
                    <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-500">Loading income…</td></tr>
                  ) : (income?.income || []).length === 0 ? (
                    <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-500">No paid orders in this range.</td></tr>
                  ) : income.income.map((row) => (
                    <tr key={row.id}>
                      <td className="px-4 py-3 text-sm">{row.date}</td>
                      <td className="px-4 py-3 text-sm capitalize">{String(row.source || '').replaceAll('_', ' ')}</td>
                      <td className="px-4 py-3 text-sm font-medium text-primary-600">{row.reference}</td>
                      <td className="px-4 py-3 text-sm">{row.customer_name || '—'}</td>
                      <td className="px-4 py-3 text-sm font-semibold">{money(row.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card overflow-hidden">
            <div className="px-4 py-3 border-b">
              <h2 className="font-semibold text-gray-900">Refunds</h2>
              <p className="text-xs text-gray-500 mt-1">
                A refund is subtracted only while its order is still counted as paid income.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    {['Date', 'Order', 'Status', 'Amount', 'In net'].map((heading) => (
                      <th key={heading} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {(income?.refunds || []).length === 0 ? (
                    <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-500">No approved refunds in this range.</td></tr>
                  ) : income.refunds.map((row) => (
                    <tr key={row.id}>
                      <td className="px-4 py-3 text-sm">{row.date}</td>
                      <td className="px-4 py-3 text-sm">{row.order_number}</td>
                      <td className="px-4 py-3 text-sm capitalize">{row.status}</td>
                      <td className="px-4 py-3 text-sm font-semibold">{money(row.amount)}</td>
                      <td className="px-4 py-3 text-sm">{row.subtracted ? 'Subtracted' : 'Already excluded'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
        )
      )}

      {tab === 'expenses' && (
        expensesError ? <LoadError title="Could not load expenses" onRetry={refetchExpenses} /> : (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b flex items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-gray-900">Expenses</h2>
              <p className="text-xs text-gray-500 mt-1">Inventory purchases are created from stock receipts. Add other business costs here.</p>
            </div>
            <button type="button" onClick={openCreate} className="btn btn-primary">
              <Plus className="w-4 h-4 mr-1" />
              Add expense
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Voucher', 'Date', 'Category', 'Description', 'Product', 'Amount', ''].map((heading) => (
                    <th key={heading || 'actions'} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {expensesLoading ? (
                  <tr><td colSpan="7" className="px-4 py-8 text-center text-gray-500">Loading expenses…</td></tr>
                ) : expenses.length === 0 ? (
                  <tr><td colSpan="7" className="px-4 py-8 text-center text-gray-500">No expenses in this range.</td></tr>
                ) : expenses.map((expense) => (
                  <tr key={expense.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-mono">{expense.voucher_number}</td>
                    <td className="px-4 py-3 text-sm">{expense.expense_date}</td>
                    <td className="px-4 py-3 text-sm">{expense.category_label}</td>
                    <td className="px-4 py-3 text-sm max-w-xs truncate">{expense.description}</td>
                    <td className="px-4 py-3 text-sm">{expense.product_name || '—'}</td>
                    <td className="px-4 py-3 text-sm font-semibold">{money(expense.amount)}</td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button type="button" onClick={() => setSelected(expense)} className="text-sm text-primary-600 mr-3">View</button>
                      <button type="button" onClick={() => printVoucher(expense)} className="text-sm text-gray-600 mr-3">Print</button>
                      <button type="button" onClick={() => openEdit(expense)} className="text-sm text-gray-600 mr-3">Edit</button>
                      {!expense.is_purchase_voucher && (
                        <button type="button" onClick={() => removeExpense(expense)} className="text-sm text-red-600">Delete</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        )
      )}

      {tab === 'profit' && (
        productFinanceError ? <LoadError title="Could not load product profit" onRetry={refetchProductFinance} /> : (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b">
            <h2 className="font-semibold text-gray-900">Product profit</h2>
            <p className="text-xs text-gray-500 mt-1">
              Actual columns use completed sales. Estimated columns use remaining stock at current selling prices.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {[
                    'Product', 'Purchased', 'Sold', 'Remaining', 'Purchase cost', 'Selling price',
                    'Sales revenue', 'Cost of goods sold', 'Realized profit', 'Est. remaining revenue', 'Est. remaining profit',
                  ].map((heading) => (
                    <th key={heading} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {productFinanceLoading ? (
                  <tr><td colSpan="11" className="px-4 py-8 text-center text-gray-500">Loading product profit…</td></tr>
                ) : productFinance.length === 0 ? (
                  <tr><td colSpan="11" className="px-4 py-8 text-center text-gray-500">No products yet.</td></tr>
                ) : productFinance.map((row) => (
                  <tr key={row.product_id} className="align-top">
                    <td className="px-4 py-3 text-sm font-medium min-w-[12rem]">
                      {row.product_name}
                      {row.reconciliation_note ? (
                        <p className="mt-1 text-xs font-normal text-gray-500">{row.reconciliation_note}</p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-sm">{row.quantity_purchased}</td>
                    <td className="px-4 py-3 text-sm">{row.quantity_sold}</td>
                    <td className="px-4 py-3 text-sm">{row.remaining_stock}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">{money(row.total_purchase_cost)}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">
                      {money(row.selling_price)}
                      {row.selling_price_varies ? <span className="block text-xs text-gray-500">Varies by variant</span> : null}
                    </td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">{money(row.total_sales_revenue)}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">{money(row.cost_of_goods_sold)}</td>
                    <td className="px-4 py-3 text-sm font-semibold whitespace-nowrap">{money(row.realized_profit)}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">{money(row.estimated_remaining_revenue)}</td>
                    <td className="px-4 py-3 text-sm font-semibold whitespace-nowrap">{money(row.estimated_remaining_profit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        )
      )}

      {tab === 'products' && (
        <section className="card overflow-hidden">
          <div className="px-4 py-3 border-b">
            <h2 className="font-semibold text-gray-900">Expense by Product</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Product', 'Expenses', 'Total'].map((heading) => (
                    <th key={heading} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {byProductLoading ? (
                  <tr><td colSpan="3" className="px-4 py-8 text-center text-gray-500">Loading…</td></tr>
                ) : byProduct.length === 0 ? (
                  <tr><td colSpan="3" className="px-4 py-8 text-center text-gray-500">No product expenses in this range.</td></tr>
                ) : byProduct.map((row) => (
                  <tr key={row.product_id || 'unassigned'}>
                    <td className="px-4 py-3 text-sm font-medium">{row.product_name}</td>
                    <td className="px-4 py-3 text-sm">{row.expense_count}</td>
                    <td className="px-4 py-3 text-sm font-semibold">{money(row.total_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {formOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
          <form onSubmit={saveExpense} className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">{editing ? 'Edit expense' : 'New expense'}</h2>
              <button type="button" onClick={() => setFormOpen(false)} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-gray-500">
                {purchaseLocked
                  ? 'This voucher was created from a stock purchase. Amount, category, product, and quantity stay tied to that receipt.'
                  : 'Use this form for costs that are not product purchases, such as delivery, packaging, marketing, and operations.'}
              </p>
              <Field label="Date">
                <input type="date" required className="input" value={form.expense_date} onChange={(event) => setForm({ ...form, expense_date: event.target.value })} />
              </Field>
              <Field label="Category">
                <select className="input" value={form.category} disabled={purchaseLocked} onChange={(event) => setForm({ ...form, category: event.target.value })}>
                  {categoryOptions.map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}
                </select>
              </Field>
              <Field label="Amount">
                <input type="number" required min="0.01" step="0.01" className="input" value={form.amount} disabled={purchaseLocked} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
              </Field>
              {purchaseLocked && (
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Quantity">
                    <input className="input bg-gray-50" value={editing.quantity ?? '—'} readOnly />
                  </Field>
                  <Field label="Unit cost">
                    <input className="input bg-gray-50" value={editing.unit_cost ?? '—'} readOnly />
                  </Field>
                </div>
              )}
              <Field label="Description">
                <textarea required rows={3} className="input" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
              </Field>
              <Field label="Payment method">
                <select className="input" value={form.payment_method} onChange={(event) => setForm({ ...form, payment_method: event.target.value })}>
                  {METHODS.map((method) => <option key={method.value || 'none'} value={method.value}>{method.label}</option>)}
                </select>
              </Field>
              <Field label="Payee">
                <input className="input" value={form.payee} onChange={(event) => setForm({ ...form, payee: event.target.value })} />
              </Field>
              <Field label="Product">
                <select className="input" value={form.product} disabled={purchaseLocked} onChange={(event) => setForm({ ...form, product: event.target.value })}>
                  <option value="">Unassigned</option>
                  {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                </select>
              </Field>
            </div>
            <div className="p-5 border-t flex justify-end gap-2">
              <button type="button" onClick={() => setFormOpen(false)} className="btn btn-secondary">Cancel</button>
              <button type="submit" disabled={saving} className="btn btn-primary">{saving ? 'Saving…' : 'Save'}</button>
            </div>
          </form>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-lg">
            <div className="p-5 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">{selected.voucher_number}</h2>
              <button type="button" onClick={() => setSelected(null)} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <dl className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <Detail label="Date" value={selected.expense_date} />
              <Detail label="Category" value={selected.category_label} />
              <Detail label="Amount" value={money(selected.amount)} />
              <Detail label="Quantity" value={selected.quantity ?? '—'} />
              <Detail label="Unit cost" value={selected.unit_cost != null ? money(selected.unit_cost) : '—'} />
              <Detail label="Payment" value={selected.payment_method_label || '—'} />
              <Detail label="Payee" value={selected.payee || '—'} />
              <Detail label="Product" value={selected.product_name || '—'} />
              <Detail label="Recorded by" value={selected.created_by_name || '—'} />
              <div className="sm:col-span-2">
                <dt className="text-gray-500">Description</dt>
                <dd className="mt-1 text-gray-900">{selected.description}</dd>
              </div>
            </dl>
            <div className="p-5 border-t flex justify-end gap-2">
              {!selected.is_purchase_voucher && (
                <button type="button" onClick={() => removeExpense(selected)} className="btn btn-secondary text-red-600">
                  <Trash2 className="w-4 h-4 mr-1" />
                  Delete
                </button>
              )}
              <button type="button" onClick={() => printVoucher(selected)} className="btn btn-primary">
                <Printer className="w-4 h-4 mr-1" />
                Print voucher
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="hidden">
        <ExpenseVoucher ref={printRef} expense={voucher} settings={settings} />
      </div>
    </AdminLayout>
  );
}

function Summary({ icon: Icon, label, value, tone, hint }) {
  const tones = {
    green: 'bg-green-100 text-green-600',
    red: 'bg-red-100 text-red-600',
    purple: 'bg-purple-100 text-purple-600',
    blue: 'bg-blue-100 text-blue-600',
  };
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {hint ? <p className="text-xs text-gray-500 mt-1">{hint}</p> : null}
        </div>
        <div className={`p-3 rounded-xl ${tones[tone]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-gray-700 mb-1">{label}</span>
      {children}
    </label>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-gray-500">{label}</dt>
      <dd className="mt-1 font-medium text-gray-900">{value}</dd>
    </div>
  );
}

const ExpenseVoucher = forwardRef(function ExpenseVoucher({ expense, settings }, ref) {
  return (
  <div ref={ref} className="voucher-sheet">
    <style>{`
      .voucher-sheet { width: 720px; padding: 32px; color: #111; font-family: "Segoe UI", Arial, sans-serif; background: #fff; }
      .voucher-sheet h1 { margin: 0; font-size: 28px; letter-spacing: 0.04em; }
      .voucher-sheet .muted { color: #555; font-size: 12px; line-height: 1.5; }
      .voucher-sheet .rule { border-top: 2px solid #111; margin: 16px 0; }
      .voucher-sheet table { width: 100%; border-collapse: collapse; }
      .voucher-sheet th, .voucher-sheet td { text-align: left; padding: 8px 0; border-bottom: 1px solid #e5e7eb; font-size: 14px; vertical-align: top; }
      .voucher-sheet th { width: 180px; color: #555; font-weight: 600; }
      .voucher-sheet .amount { font-size: 22px; font-weight: 700; }
      .voucher-sheet .signs { display: flex; justify-content: space-between; gap: 48px; margin-top: 64px; }
      .voucher-sheet .sign { flex: 1; border-top: 1px solid #111; padding-top: 8px; font-size: 12px; color: #555; }
    `}</style>
    <h1>PickOrbeet</h1>
    <p className="muted">
      {settings?.contact_address}<br />
      {[settings?.contact_phone_1, settings?.contact_email_1].filter(Boolean).join(' · ')}
    </p>
    <div className="rule" />
    <p style={{ fontWeight: 700, letterSpacing: '0.08em' }}>EXPENSE VOUCHER</p>
    {expense ? (
      <table>
        <tbody>
          <tr><th>Voucher number</th><td>{expense.voucher_number}</td></tr>
          <tr><th>Date</th><td>{expense.expense_date}</td></tr>
          <tr><th>Category</th><td>{expense.category_label}</td></tr>
          <tr><th>Product</th><td>{expense.product_name || '—'}</td></tr>
          <tr><th>Description</th><td>{expense.description}</td></tr>
          {expense.quantity != null ? <tr><th>Quantity</th><td>{expense.quantity}</td></tr> : null}
          {expense.unit_cost != null ? <tr><th>Unit cost</th><td>{money(expense.unit_cost)}</td></tr> : null}
          <tr><th>Amount</th><td className="amount">{money(expense.amount)}</td></tr>
          <tr><th>Payment method</th><td>{expense.payment_method_label || '—'}</td></tr>
          <tr><th>Payee</th><td>{expense.payee || '—'}</td></tr>
        </tbody>
      </table>
    ) : null}
    <div className="signs">
      <div className="sign">Authorized by</div>
      <div className="sign">Signature</div>
    </div>
  </div>
  );
});
