import { forwardRef, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  BarChart3, Calendar, Check, Minus, Package, Plus, Printer, Receipt,
  RotateCcw, ShoppingBag, ShoppingCart, Trash2, Upload, Users, Wallet, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useReactToPrint } from 'react-to-print';
import AdminLayout from '@/components/layout/AdminLayout';
import LoadError from '@/components/ui/LoadError';
import SearchableSelect from '@/components/ui/SearchableSelect';
import { getMediaUrl } from '@/lib/utils';
import { useGetInventoryItemsQuery, useGetStoreSettingsQuery } from '@/store/api/productsApi';
import {
  useCreateExpenseMutation,
  useCreateManualIncomeMutation,
  useCreatePurchaseReceiptMutation,
  useDeleteExpenseMutation,
  useDeleteManualIncomeMutation,
  useGetExpensesByProductQuery,
  useGetExpensesQuery,
  useGetIncomeQuery,
  useGetProductFinanceQuery,
  useRecordProductCostMutation,
  useUpdateExpenseMutation,
  useUpdateManualIncomeMutation,
  useUpdatePurchaseReceiptMutation,
} from '@/store/api/paymentsApi';

const EXPENSE_CATEGORIES = [
  { value: 'product_buying', label: 'Product Buying' },
  { value: 'packaging', label: 'Packaging' },
  { value: 'transportation', label: 'Transportation' },
  { value: 'others', label: 'Others' },
];

const SHARE_PARTNERS = [
  { value: 'orbeetal', label: 'Orbeetal' },
  { value: 'rakib', label: 'Rakib' },
  { value: 'tasdiq', label: 'Tasdiq' },
  { value: 'mayeen', label: 'Mayeen' },
  { value: 'nahiyan', label: 'Nahiyan' },
];

const METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'card', label: 'Card' },
  { value: 'mobile_banking', label: 'Mobile Banking' },
  { value: '', label: 'Not specified' },
];

let lineKey = 0;
function emptyPurchaseLine() {
  lineKey += 1;
  return {
    key: `line-${lineKey}`,
    product: '',
    variant: '',
    quantity: '1',
    unit_cost: '',
    discount_type: 'percent',
    discount_value: '',
  };
}

const emptyExpenseForm = {
  expense_date: new Date().toISOString().split('T')[0],
  category: 'product_buying',
  description: '',
  comments: '',
  amount: '',
  payment_method: 'cash',
  payee: '',
  product: '',
  invoice_number: '',
  additional_discount_type: 'percent',
  additional_discount_value: '',
  lines: [emptyPurchaseLine()],
};

function lineAmounts(line) {
  const quantity = Math.max(0, parseInt(line.quantity, 10) || 0);
  const unitCost = Number(line.unit_cost) || 0;
  const discountValue = Number(line.discount_value) || 0;
  const subtotal = quantity * unitCost;
  let discountAmount = 0;
  if (discountValue > 0 && line.discount_type === 'percent') {
    discountAmount = subtotal * Math.min(discountValue, 100) / 100;
  } else if (discountValue > 0 && line.discount_type === 'fixed') {
    discountAmount = Math.min(discountValue, subtotal);
  }
  const total = Math.max(0, subtotal - discountAmount);
  return { quantity, subtotal, discountAmount, total };
}

function RequiredMark() {
  return <span className="text-red-500"> *</span>;
}

function buildFinanceBody(fields, { file = null, clearProof = false } = {}) {
  if (!file && !clearProof) return fields;
  const body = new FormData();
  Object.entries(fields).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    if (key === 'line_inputs') {
      body.append(key, JSON.stringify(value));
      return;
    }
    body.append(key, value);
  });
  if (file) body.append('payment_proof', file);
  if (clearProof) body.append('clear_payment_proof', 'true');
  return body;
}

function receiptTotals(lines, additionalDiscountType = 'percent', additionalDiscountValue = '') {
  const base = (lines || []).reduce(
    (acc, line) => {
      const amounts = lineAmounts(line);
      acc.totalQuantity += amounts.quantity;
      acc.subtotal += amounts.subtotal;
      acc.totalDiscount += amounts.discountAmount;
      acc.linesTotal += amounts.total;
      return acc;
    },
    { totalQuantity: 0, subtotal: 0, totalDiscount: 0, linesTotal: 0 },
  );
  const discountValue = Number(additionalDiscountValue) || 0;
  let additionalDiscount = 0;
  if (discountValue > 0 && additionalDiscountType === 'percent') {
    additionalDiscount = base.linesTotal * Math.min(discountValue, 100) / 100;
  } else if (discountValue > 0 && additionalDiscountType === 'fixed') {
    additionalDiscount = Math.min(discountValue, base.linesTotal);
  }
  if (additionalDiscount >= base.linesTotal && base.linesTotal > 0) {
    additionalDiscount = Math.max(0, base.linesTotal - 0.01);
  }
  return {
    ...base,
    additionalDiscount,
    grandTotal: Math.max(0, base.linesTotal - additionalDiscount),
  };
}

const emptyIncomeForm = {
  income_date: new Date().toISOString().split('T')[0],
  category: 'share',
  share_partner: 'orbeetal',
  description: '',
  comments: '',
  amount: '',
};

function money(value) {
  if (value == null) return '—';
  return `৳${Number(value || 0).toLocaleString()}`;
}

function errorText(error, fallback = 'Could not save') {
  const data = error?.data;
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  const first = Object.values(data)[0];
  if (Array.isArray(first)) return first[0];
  if (first && typeof first === 'object') return Object.values(first)[0];
  return fallback;
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
  const [incomeSource, setIncomeSource] = useState('product'); // product | share
  const [expenseFormOpen, setExpenseFormOpen] = useState(false);
  const [incomeFormOpen, setIncomeFormOpen] = useState(false);
  const [editingExpense, setEditingExpense] = useState(null);
  const [editingIncome, setEditingIncome] = useState(null);
  const [expenseForm, setExpenseForm] = useState(emptyExpenseForm);
  const [incomeForm, setIncomeForm] = useState(emptyIncomeForm);
  const [expenseProofFile, setExpenseProofFile] = useState(null);
  const [expenseProofUrl, setExpenseProofUrl] = useState('');
  const [clearExpenseProof, setClearExpenseProof] = useState(false);
  const [incomeProofFile, setIncomeProofFile] = useState(null);
  const [incomeProofUrl, setIncomeProofUrl] = useState('');
  const [clearIncomeProof, setClearIncomeProof] = useState(false);
  const [selected, setSelected] = useState(null);
  const [printItems, setPrintItems] = useState([]);
  const [shouldPrint, setShouldPrint] = useState(false);
  const [selectedExpenseIds, setSelectedExpenseIds] = useState([]);
  const [selectedIncomeIds, setSelectedIncomeIds] = useState([]);
  const [costForm, setCostForm] = useState(null);
  const printRef = useRef(null);

  const { data: income, isLoading: incomeLoading, isError: incomeError, refetch: refetchIncome } = useGetIncomeQuery(dateRange);
  const { data: expensesData, isLoading: expensesLoading, isError: expensesError, refetch: refetchExpenses } = useGetExpensesQuery(dateRange);
  const { data: byProduct = [], isLoading: byProductLoading } = useGetExpensesByProductQuery(dateRange);
  const { data: productFinance = [], isLoading: productFinanceLoading, isError: productFinanceError, refetch: refetchProductFinance } = useGetProductFinanceQuery();
  const { data: settings } = useGetStoreSettingsQuery();
  const { data: inventory } = useGetInventoryItemsQuery({}, { skip: !expenseFormOpen });
  const [createExpense, { isLoading: creatingExpense }] = useCreateExpenseMutation();
  const [updateExpense, { isLoading: updatingExpense }] = useUpdateExpenseMutation();
  const [deleteExpense] = useDeleteExpenseMutation();
  const [createPurchaseReceipt, { isLoading: creatingReceipt }] = useCreatePurchaseReceiptMutation();
  const [updatePurchaseReceipt, { isLoading: updatingReceipt }] = useUpdatePurchaseReceiptMutation();
  const [createManualIncome, { isLoading: creatingIncome }] = useCreateManualIncomeMutation();
  const [updateManualIncome, { isLoading: updatingIncome }] = useUpdateManualIncomeMutation();
  const [deleteManualIncome] = useDeleteManualIncomeMutation();
  const [recordProductCost, { isLoading: recordingCost }] = useRecordProductCostMutation();

  const expenses = rowsOf(expensesData);
  const products = inventory?.items || [];
  const isProductBuying = expenseForm.category === 'product_buying';
  const editingReceipt = editingExpense?.purchase_receipt || null;
  const purchaseLocked = Boolean(editingExpense?.is_purchase_voucher && !editingReceipt);
  const receiptEditable = isProductBuying && (!editingExpense || Boolean(editingReceipt));
  const savingExpense = creatingExpense || updatingExpense || creatingReceipt || updatingReceipt;
  const savingIncome = creatingIncome || updatingIncome;
  const categoryOptions = editingExpense?.category === 'inventory_purchase'
    ? [{ value: 'inventory_purchase', label: 'Inventory Purchase' }, ...EXPENSE_CATEGORIES]
    : EXPENSE_CATEGORIES;
  const purchaseSummary = receiptTotals(
    expenseForm.lines,
    expenseForm.additional_discount_type,
    expenseForm.additional_discount_value,
  );

  const handlePrint = useReactToPrint({ content: () => printRef.current });

  useEffect(() => {
    if (shouldPrint && printItems.length > 0) {
      handlePrint();
      setShouldPrint(false);
    }
  }, [shouldPrint, printItems, handlePrint]);

  useEffect(() => {
    setSelectedExpenseIds([]);
  }, [dateRange.start_date, dateRange.end_date, tab]);

  useEffect(() => {
    setSelectedIncomeIds([]);
  }, [dateRange.start_date, dateRange.end_date, incomeSource]);

  const openCreateExpense = () => {
    setEditingExpense(null);
    setExpenseForm({ ...emptyExpenseForm, lines: [emptyPurchaseLine()] });
    setExpenseProofFile(null);
    setExpenseProofUrl('');
    setClearExpenseProof(false);
    setExpenseFormOpen(true);
  };

  const openEditExpense = (expense) => {
    setEditingExpense(expense);
    const receipt = expense.purchase_receipt;
    setExpenseForm({
      expense_date: receipt?.purchase_date || expense.expense_date,
      category: expense.category,
      description: expense.description,
      comments: receipt?.comments ?? expense.comments ?? '',
      amount: expense.amount,
      payment_method: receipt?.payment_method || expense.payment_method || '',
      payee: receipt?.payee || expense.payee || '',
      product: expense.product || '',
      invoice_number: receipt?.invoice_number || '',
      additional_discount_type: receipt?.additional_discount_type === 'fixed' ? 'fixed' : 'percent',
      additional_discount_value: receipt?.additional_discount_type === 'none' || !Number(receipt?.additional_discount_value)
        ? ''
        : String(receipt?.additional_discount_value ?? ''),
      lines: receipt?.lines?.length
        ? receipt.lines.map((line) => {
          lineKey += 1;
          const discountType = line.discount_type === 'fixed' ? 'fixed' : 'percent';
          return {
            key: `line-${lineKey}`,
            product: line.product || '',
            variant: line.variant || '',
            quantity: String(line.quantity ?? 1),
            unit_cost: String(line.unit_cost ?? ''),
            discount_type: discountType,
            discount_value: line.discount_type === 'none' || !Number(line.discount_value)
              ? ''
              : String(line.discount_value ?? ''),
          };
        })
        : [emptyPurchaseLine()],
    });
    setExpenseProofFile(null);
    setExpenseProofUrl(expense.payment_proof || receipt?.payment_proof || '');
    setClearExpenseProof(false);
    setExpenseFormOpen(true);
  };

  const updatePurchaseLine = (key, patch) => {
    setExpenseForm((current) => ({
      ...current,
      lines: current.lines.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    }));
  };

  const addPurchaseLine = () => {
    setExpenseForm((current) => ({
      ...current,
      lines: [...current.lines, emptyPurchaseLine()],
    }));
  };

  const removePurchaseLine = (key) => {
    setExpenseForm((current) => ({
      ...current,
      lines: current.lines.length <= 1
        ? current.lines
        : current.lines.filter((line) => line.key !== key),
    }));
  };

  const openCreateIncome = () => {
    setEditingIncome(null);
    setIncomeForm({ ...emptyIncomeForm, category: 'share' });
    setIncomeProofFile(null);
    setIncomeProofUrl('');
    setClearIncomeProof(false);
    setIncomeFormOpen(true);
  };

  const openEditIncome = (row) => {
    if (row.entry_type !== 'manual') return;
    setEditingIncome(row);
    setIncomeForm({
      income_date: row.date,
      category: 'share',
      share_partner: row.share_partner || 'orbeetal',
      description: row.description || '',
      comments: row.comments || '',
      amount: row.amount,
    });
    setIncomeProofFile(null);
    setIncomeProofUrl(row.payment_proof || '');
    setClearIncomeProof(false);
    setIncomeFormOpen(true);
  };

  const toExpensePrintItem = (expense) => ({
    kind: 'expense',
    id: expense.id,
    voucher_number: expense.voucher_number,
    date: expense.expense_date,
    category_label: expense.category_label,
    description: expense.description,
    comments: expense.comments,
    amount: expense.amount,
    payment_method_label: expense.payment_method_label,
    payee: expense.payee,
    product_name: expense.product_name,
    quantity: expense.quantity,
    unit_cost: expense.unit_cost,
    purchase_receipt: expense.purchase_receipt,
  });

  const toIncomePrintItem = (row) => ({
    kind: 'income',
    id: row.id,
    voucher_number: row.voucher_number || row.reference,
    date: row.date,
    category_label: row.category_label || 'Share Amount',
    description: row.description,
    comments: row.comments,
    amount: row.amount,
    payment_method_label: '',
    share_partner_label: row.share_partner_label,
    created_by_name: row.created_by_name,
  });

  const printVouchers = (items) => {
    if (!items.length) {
      toast.error('Select at least one voucher to print');
      return;
    }
    setPrintItems(items);
    setShouldPrint(true);
  };

  const printExpenseVoucher = (expense) => printVouchers([toExpensePrintItem(expense)]);
  const printIncomeVoucher = (row) => printVouchers([toIncomePrintItem(row)]);

  const toggleExpenseSelected = (id) => {
    setSelectedExpenseIds((current) => (
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
    ));
  };

  const toggleIncomeSelected = (id) => {
    setSelectedIncomeIds((current) => (
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
    ));
  };

  const printSelectedExpenses = () => {
    const items = expenses
      .filter((expense) => selectedExpenseIds.includes(expense.id))
      .map(toExpensePrintItem);
    printVouchers(items);
  };

  const printSelectedIncome = () => {
    const manualRows = (income?.income || []).filter((row) => row.entry_type === 'manual');
    const items = manualRows
      .filter((row) => selectedIncomeIds.includes(row.id))
      .map(toIncomePrintItem);
    printVouchers(items);
  };

  const saveExpense = async (event) => {
    event.preventDefault();
    if (isProductBuying && receiptEditable) {
      if (!(expenseForm.payee || '').trim()) {
        toast.error('Dealer/seller name is required for Product Buying');
        return;
      }
      if (!expenseForm.lines.length) {
        toast.error('Add at least one product line');
        return;
      }
      for (const line of expenseForm.lines) {
        const product = products.find((item) => item.id === line.product);
        if (!line.product) {
          toast.error('Select a product for every line');
          return;
        }
        if (product?.has_variants && !line.variant) {
          toast.error(`Select a variant for ${product.name}`);
          return;
        }
        if (!(Number(line.quantity) > 0) || !(Number(line.unit_cost) > 0)) {
          toast.error('Each product needs quantity and unit buying price');
          return;
        }
      }
      if (!(purchaseSummary.grandTotal > 0)) {
        toast.error('Grand total must be greater than zero');
        return;
      }
      const additionalDiscountValue = Number(expenseForm.additional_discount_value) || 0;
      const receiptPayload = buildFinanceBody({
        purchase_date: expenseForm.expense_date,
        payee: expenseForm.payee.trim(),
        invoice_number: expenseForm.invoice_number || '',
        comments: expenseForm.comments || '',
        payment_method: expenseForm.payment_method || '',
        stock_location: 'warehouse',
        additional_discount_type: additionalDiscountValue > 0
          ? (expenseForm.additional_discount_type || 'percent')
          : 'none',
        additional_discount_value: additionalDiscountValue > 0 ? additionalDiscountValue : 0,
        line_inputs: expenseForm.lines.map((line) => {
          const discountValue = Number(line.discount_value) || 0;
          return {
            product: line.product,
            variant: line.variant || null,
            quantity: parseInt(line.quantity, 10),
            unit_cost: line.unit_cost,
            discount_type: discountValue > 0 ? (line.discount_type || 'percent') : 'none',
            discount_value: discountValue > 0 ? discountValue : 0,
          };
        }),
      }, { file: expenseProofFile, clearProof: clearExpenseProof });
      try {
        if (editingReceipt) {
          await updatePurchaseReceipt({ id: editingReceipt.id, data: receiptPayload }).unwrap();
          toast.success('Purchase receipt updated');
        } else {
          const created = await createPurchaseReceipt(receiptPayload).unwrap();
          toast.success(
            `Purchase ${created.voucher_number || created.receipt_number} recorded and stock updated`,
          );
        }
        setExpenseFormOpen(false);
      } catch (error) {
        toast.error(errorText(error, 'Could not save the purchase receipt'));
      }
      return;
    }

    const payload = buildFinanceBody({
      expense_date: expenseForm.expense_date,
      category: expenseForm.category,
      description: expenseForm.description,
      amount: expenseForm.amount,
      product: expenseForm.product || null,
      payment_method: expenseForm.payment_method || '',
      comments: expenseForm.comments || '',
      payee: expenseForm.payee || '',
    }, { file: expenseProofFile, clearProof: clearExpenseProof });
    try {
      if (editingExpense) {
        await updateExpense({ id: editingExpense.id, data: payload }).unwrap();
        toast.success('Expense updated');
      } else {
        const created = await createExpense(payload).unwrap();
        toast.success(`Expense ${created.voucher_number} recorded`);
      }
      setExpenseFormOpen(false);
    } catch (error) {
      toast.error(errorText(error, 'Could not save the expense'));
    }
  };

  const saveIncome = async (event) => {
    event.preventDefault();
    const payload = buildFinanceBody({
      income_date: incomeForm.income_date,
      category: 'share',
      share_partner: incomeForm.share_partner,
      description: incomeForm.description || '',
      comments: incomeForm.comments || '',
      amount: incomeForm.amount,
    }, { file: incomeProofFile, clearProof: clearIncomeProof });
    try {
      if (editingIncome) {
        await updateManualIncome({ id: editingIncome.id, data: payload }).unwrap();
        toast.success('Income updated');
      } else {
        const created = await createManualIncome(payload).unwrap();
        toast.success(`Income ${created.voucher_number} recorded`);
      }
      setIncomeFormOpen(false);
    } catch (error) {
      toast.error(errorText(error, 'Could not save the income'));
    }
  };

  const removeExpense = async (expense) => {
    const isReceipt = Boolean(expense.purchase_receipt_id || expense.purchase_receipt);
    const message = isReceipt
      ? `Cancel purchase ${expense.voucher_number}? This reverses the inventory added by this receipt and removes the expense.`
      : `Delete voucher ${expense.voucher_number}?`;
    if (!confirm(message)) return;
    try {
      await deleteExpense(expense.id).unwrap();
      if (selected?.id === expense.id) setSelected(null);
      toast.success(isReceipt ? 'Purchase cancelled and stock reversed' : 'Expense deleted');
    } catch (error) {
      toast.error(errorText(error, 'Could not delete the expense'));
    }
  };

  const removeIncome = async (row) => {
    if (row.entry_type !== 'manual') return;
    if (!confirm(`Delete income ${row.reference}?`)) return;
    try {
      await deleteManualIncome(row.id).unwrap();
      toast.success('Income deleted');
    } catch (error) {
      toast.error(errorText(error, 'Could not delete the income'));
    }
  };

  const openCostForm = (row) => {
    setCostForm({
      product_id: row.product_id,
      product_name: row.product_name,
      unit_cost: row.suggested_unit_cost || '',
    });
  };

  const saveProductCost = async (event) => {
    event.preventDefault();
    if (!costForm) return;
    try {
      const result = await recordProductCost({
        productId: costForm.product_id,
        unit_cost: costForm.unit_cost,
      }).unwrap();
      toast.success(
        result.units_recorded
          ? `Recorded cost for ${result.units_recorded} units of ${costForm.product_name}`
          : `Purchase cost saved for ${costForm.product_name}`,
      );
      setCostForm(null);
    } catch (error) {
      toast.error(errorText(error, 'Could not record purchase cost'));
    }
  };

  const orderIncomeRows = (income?.income || []).filter((row) => row.entry_type === 'order');
  const shareIncomeRows = (income?.income || []).filter((row) => row.entry_type === 'manual');
  const refundRows = income?.refunds || [];
  const refundsTotal = refundRows.reduce((sum, row) => sum + Number(row.amount || 0), 0);

  const primaryTabs = [
    { id: 'income', label: 'Income', Icon: Wallet },
    { id: 'expenses', label: 'Expenses', Icon: Receipt },
    { id: 'profit', label: 'Product Profit', Icon: BarChart3 },
    { id: 'products', label: 'Expenses by Product', Icon: Package },
  ];
  const incomeTabs = [
    { id: 'product', label: 'Product Selling', Icon: ShoppingCart },
    { id: 'share', label: 'Share Amount', Icon: Users },
  ];

  const pillClass = (active) => (
    active
      ? 'bg-primary-500 text-white shadow-sm'
      : 'bg-[#EEF1F7] text-gray-700 hover:bg-[#E4E9F2]'
  );

  return (
    <AdminLayout title="Finance">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#E8EEFF] text-sidebar-bg">
              <BarChart3 className="h-5 w-5" />
            </span>
            <h1 className="text-2xl font-bold text-gray-900">Finance</h1>
          </div>
          <p className="mt-2 text-sm text-gray-500">
            Record income and expenses, and review product profit.
            {' '}
            <Link href="/finance/summary" className="font-semibold text-primary-500 hover:text-primary-600">
              View financial summary &amp; transactions report →
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative inline-flex items-center">
            <Calendar className="pointer-events-none absolute left-3 h-4 w-4 text-gray-400" />
            <input
              type="date"
              value={dateRange.start_date}
              onChange={(event) => setDateRange({ ...dateRange, start_date: event.target.value })}
              className="input w-auto pl-9"
              aria-label="From date"
            />
          </label>
          <span className="text-sm text-gray-400">to</span>
          <label className="relative inline-flex items-center">
            <Calendar className="pointer-events-none absolute left-3 h-4 w-4 text-gray-400" />
            <input
              type="date"
              value={dateRange.end_date}
              onChange={(event) => setDateRange({ ...dateRange, end_date: event.target.value })}
              className="input w-auto pl-9"
              aria-label="To date"
            />
          </label>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {primaryTabs.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${pillClass(tab === id)}`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === 'income' && (
        incomeError ? <LoadError title="Could not load income" onRetry={refetchIncome} /> : (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            {incomeTabs.map(({ id, label, Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setIncomeSource(id)}
                className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
                  incomeSource === id
                    ? 'bg-primary-500 text-white shadow-sm'
                    : 'border border-[#D8DEEA] bg-white text-gray-700 hover:bg-[#F7F9FC]'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>

          {incomeSource === 'product' ? (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/80 p-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
                      <ShoppingCart className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-xs font-medium text-emerald-800/80">Total Product Sales</p>
                      <p className="text-2xl font-bold text-emerald-700">{money(income?.income_total || 0)}</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-sky-100 bg-sky-50/80 p-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-100 text-sky-700">
                      <ShoppingBag className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-xs font-medium text-sky-800/80">Orders</p>
                      <p className="text-2xl font-bold text-sidebar-bg">{orderIncomeRows.length}</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-violet-100 bg-violet-50/80 p-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
                      <RotateCcw className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-xs font-medium text-violet-800/80">Refunds (Approved)</p>
                      <p className="text-2xl font-bold text-violet-700">{money(refundsTotal)}</p>
                    </div>
                  </div>
                </div>
              </div>

              <section className="overflow-hidden rounded-2xl border border-[#DCE4F2] bg-white shadow-sm">
                <div className="border-b border-[#E8EEF8] px-5 py-4">
                  <div className="flex items-center gap-2">
                    <ShoppingCart className="h-4 w-4 text-sidebar-bg" />
                    <h2 className="font-semibold text-gray-900">Product Selling</h2>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Automatically synced from paid orders. Admins cannot add product-selling income manually.
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-[#F3F7FD]">
                        {['Order ID', 'Customer', 'Order date', 'Selling amount', 'Payment status'].map((heading) => (
                          <th key={heading} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">{heading}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#EEF2F8]">
                      {incomeLoading ? (
                        <tr><td colSpan="5" className="px-5 py-10 text-center text-sm text-gray-500">Loading product sales…</td></tr>
                      ) : orderIncomeRows.length === 0 ? (
                        <tr>
                          <td colSpan="5" className="px-5 py-12 text-center">
                            <Package className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                            <p className="text-sm text-gray-500">No paid product orders in this range.</p>
                          </td>
                        </tr>
                      ) : orderIncomeRows.map((row) => (
                        <tr key={`order-${row.id}`} className="hover:bg-[#F8FAFD]">
                          <td className="px-5 py-3.5 text-sm font-semibold text-primary-600">
                            <Link href={`/orders/${row.order_id || row.id}`}>{row.order_number || row.reference}</Link>
                          </td>
                          <td className="px-5 py-3.5 text-sm text-gray-800">{row.customer_name || '—'}</td>
                          <td className="px-5 py-3.5 text-sm text-gray-600">{row.order_date || row.date}</td>
                          <td className="px-5 py-3.5 text-sm font-bold text-emerald-600">{money(row.amount)}</td>
                          <td className="px-5 py-3.5 text-sm">
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold capitalize text-emerald-700">
                              <Check className="h-3.5 w-3.5" />
                              {row.payment_status || 'paid'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!incomeLoading && income ? (
                  <div className="border-t border-[#DCE4F2] bg-[#F3F7FD] px-5 py-3 text-sm font-semibold text-sidebar-bg">
                    Total product sales: {money(income.income_total)}
                  </div>
                ) : null}
              </section>

              <section className="overflow-hidden rounded-2xl border border-[#DCE4F2] bg-white shadow-sm">
                <div className="border-b border-[#E8EEF8] px-5 py-4">
                  <div className="flex items-center gap-2">
                    <RotateCcw className="h-4 w-4 text-violet-600" />
                    <h2 className="font-semibold text-gray-900">Refunds</h2>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    A refund is subtracted only while its order is still counted as paid product sales.
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-[#F3F7FD]">
                        {['Date', 'Order', 'Status', 'Amount', 'In net'].map((heading) => (
                          <th key={heading} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">{heading}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#EEF2F8]">
                      {refundRows.length === 0 ? (
                        <tr>
                          <td colSpan="5" className="px-5 py-12 text-center">
                            <Package className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                            <p className="text-sm text-gray-500">No approved refunds in this range.</p>
                          </td>
                        </tr>
                      ) : refundRows.map((row) => (
                        <tr key={row.id} className="hover:bg-[#F8FAFD]">
                          <td className="px-5 py-3.5 text-sm text-gray-700">{row.date}</td>
                          <td className="px-5 py-3.5 text-sm font-medium text-primary-600">{row.order_number}</td>
                          <td className="px-5 py-3.5 text-sm capitalize text-gray-700">{row.status}</td>
                          <td className="px-5 py-3.5 text-sm font-bold text-violet-700">{money(row.amount)}</td>
                          <td className="px-5 py-3.5 text-sm text-gray-600">{row.subtracted ? 'Subtracted' : 'Already excluded'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : (
            <section className="overflow-hidden rounded-2xl border border-[#DCE4F2] bg-white shadow-sm">
              <div className="flex flex-col gap-3 border-b border-[#E8EEF8] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-sidebar-bg" />
                    <h2 className="font-semibold text-gray-900">Share Amount</h2>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Manually record shareholder contributions from Orbeetal, Rakib, Tasdiq, Mayeen, or Nahiyan.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={printSelectedIncome}
                    disabled={selectedIncomeIds.length === 0}
                    className="btn btn-secondary"
                  >
                    <Printer className="mr-1 h-4 w-4" />
                    Print selected{selectedIncomeIds.length ? ` (${selectedIncomeIds.length})` : ''}
                  </button>
                  <button type="button" onClick={openCreateIncome} className="btn btn-primary">
                    <Plus className="mr-1 h-4 w-4" />
                    Add share amount
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-[#F3F7FD]">
                      <th className="px-5 py-3 w-10">
                        <span className="sr-only">Select</span>
                      </th>
                      {['Date', 'Shareholder', 'Description', 'Comments', 'Amount', 'Reference', ''].map((heading) => (
                        <th key={heading || 'actions'} className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#EEF2F8]">
                    {incomeLoading ? (
                      <tr><td colSpan="8" className="px-5 py-10 text-center text-sm text-gray-500">Loading share amounts…</td></tr>
                    ) : shareIncomeRows.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="px-5 py-12 text-center">
                          <Package className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                          <p className="text-sm text-gray-500">No share amounts in this range.</p>
                        </td>
                      </tr>
                    ) : shareIncomeRows.map((row) => (
                      <tr key={`manual-${row.id}`} className="hover:bg-[#F8FAFD]">
                        <td className="px-5 py-3.5">
                          <input
                            type="checkbox"
                            checked={selectedIncomeIds.includes(row.id)}
                            onChange={() => toggleIncomeSelected(row.id)}
                            aria-label={`Select ${row.reference}`}
                          />
                        </td>
                        <td className="px-5 py-3.5 text-sm text-gray-700">{row.date}</td>
                        <td className="px-5 py-3.5 text-sm font-medium text-gray-900">{row.share_partner_label || '—'}</td>
                        <td className="max-w-xs truncate px-5 py-3.5 text-sm text-gray-700">{row.description || '—'}</td>
                        <td className="max-w-xs truncate px-5 py-3.5 text-sm text-gray-600">{row.comments || '—'}</td>
                        <td className="px-5 py-3.5 text-sm font-bold text-emerald-600">{money(row.amount)}</td>
                        <td className="px-5 py-3.5 font-mono text-xs text-gray-500">{row.reference}</td>
                        <td className="whitespace-nowrap px-5 py-3.5 text-right">
                          <button type="button" onClick={() => printIncomeVoucher(row)} className="mr-3 text-sm text-gray-600">Print</button>
                          <button type="button" onClick={() => openEditIncome(row)} className="mr-3 text-sm text-gray-600">Edit</button>
                          <button type="button" onClick={() => removeIncome(row)} className="text-sm text-red-600">Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!incomeLoading && income ? (
                <div className="border-t border-[#DCE4F2] bg-[#F3F7FD] px-5 py-3 text-sm font-semibold text-sidebar-bg">
                  Total share amount: {money(income.manual_income_total)}
                </div>
              ) : null}
            </section>
          )}
        </div>
        )
      )}

      {tab === 'expenses' && (
        expensesError ? <LoadError title="Could not load expenses" onRetry={refetchExpenses} /> : (
        <section className="overflow-hidden rounded-2xl border border-[#DCE4F2] bg-white shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-[#E8EEF8] px-5 py-4">
            <div>
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-sidebar-bg" />
                <h2 className="font-semibold text-gray-900">Expenses</h2>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Product Buying posts a purchase receipt and updates warehouse or dealer stock automatically. Packaging, Transportation, and Other costs stay finance-only.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={printSelectedExpenses}
                disabled={selectedExpenseIds.length === 0}
                className="btn btn-secondary"
              >
                <Printer className="w-4 h-4 mr-1" />
                Print selected{selectedExpenseIds.length ? ` (${selectedExpenseIds.length})` : ''}
              </button>
              <button type="button" onClick={openCreateExpense} className="btn btn-primary">
                <Plus className="w-4 h-4 mr-1" />
                Add expense
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 w-10">
                    <span className="sr-only">Select</span>
                  </th>
                  {['Voucher', 'Date', 'Category', 'Description', 'Dealer / Product', 'Amount', ''].map((heading) => (
                    <th key={heading || 'actions'} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {expensesLoading ? (
                  <tr><td colSpan="8" className="px-4 py-8 text-center text-gray-500">Loading expenses…</td></tr>
                ) : expenses.length === 0 ? (
                  <tr><td colSpan="8" className="px-4 py-8 text-center text-gray-500">No expenses in this range.</td></tr>
                ) : expenses.map((expense) => (
                  <tr key={expense.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedExpenseIds.includes(expense.id)}
                        onChange={() => toggleExpenseSelected(expense.id)}
                        aria-label={`Select ${expense.voucher_number}`}
                      />
                    </td>
                    <td className="px-4 py-3 text-sm font-mono">{expense.voucher_number}</td>
                    <td className="px-4 py-3 text-sm">{expense.expense_date}</td>
                    <td className="px-4 py-3 text-sm">{expense.category_label}</td>
                    <td className="px-4 py-3 text-sm max-w-xs truncate">{expense.description}</td>
                    <td className="px-4 py-3 text-sm">
                      {expense.payee || expense.product_name || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm font-semibold text-red-700">{money(expense.amount)}</td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button type="button" onClick={() => setSelected(expense)} className="text-sm text-primary-600 mr-3">View</button>
                      <button type="button" onClick={() => printExpenseVoucher(expense)} className="text-sm text-gray-600 mr-3">Print</button>
                      <button type="button" onClick={() => openEditExpense(expense)} className="text-sm text-gray-600 mr-3">Edit</button>
                      {(!expense.is_purchase_voucher || expense.purchase_receipt_id || expense.purchase_receipt) && (
                        <button type="button" onClick={() => removeExpense(expense)} className="text-sm text-red-600">
                          {expense.purchase_receipt_id || expense.purchase_receipt ? 'Cancel' : 'Delete'}
                        </button>
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
            <h2 className="font-semibold text-gray-900">Product Profit</h2>
            <p className="text-xs text-gray-500 mt-1">
              Purchase cost comes from product buying vouchers. Sold units and revenue come from completed paid orders.
              Admin panel sales appear on a separate row when the selling price may differ from the catalog.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {[
                    'Product', 'Channel', 'Purchased', 'Sold', 'Remaining', 'Purchase cost', 'Selling price',
                    'Sales revenue', 'Cost of goods sold', 'Realized profit', 'Est. remaining revenue', 'Est. remaining profit', '',
                  ].map((heading) => (
                    <th key={heading || 'actions'} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {productFinanceLoading ? (
                  <tr><td colSpan="13" className="px-4 py-8 text-center text-gray-500">Loading product profit…</td></tr>
                ) : productFinance.length === 0 ? (
                  <tr><td colSpan="13" className="px-4 py-8 text-center text-gray-500">No products yet.</td></tr>
                ) : productFinance.map((row) => (
                  <tr key={row.row_id || `${row.product_id}:${row.sale_channel}`} className="align-top">
                    <td className="px-4 py-3 text-sm font-medium min-w-[12rem]">
                      {row.product_name}
                      {row.reconciliation_note ? (
                        <p className="mt-1 text-xs font-normal text-gray-500">{row.reconciliation_note}</p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium ${
                        row.sale_channel === 'admin'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-sky-100 text-sky-800'
                      }`}>
                        {row.sale_channel_label || (row.sale_channel === 'admin' ? 'Admin panel' : 'Storefront')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">{row.quantity_purchased == null ? '—' : row.quantity_purchased}</td>
                    <td className="px-4 py-3 text-sm">{row.quantity_sold}</td>
                    <td className="px-4 py-3 text-sm">{row.remaining_stock == null ? '—' : row.remaining_stock}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">
                      {row.total_purchase_cost == null ? '—' : money(row.total_purchase_cost)}
                    </td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">
                      {money(row.avg_selling_price || row.selling_price)}
                      {row.sale_channel === 'admin' ? (
                        <span className="block text-xs text-gray-500">Avg. order price</span>
                      ) : null}
                      {row.selling_price_varies ? <span className="block text-xs text-gray-500">Varies by variant</span> : null}
                    </td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">{money(row.total_sales_revenue)}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">{money(row.cost_of_goods_sold)}</td>
                    <td className="px-4 py-3 text-sm font-semibold whitespace-nowrap">{money(row.realized_profit)}</td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">
                      {row.estimated_remaining_revenue == null ? '—' : money(row.estimated_remaining_revenue)}
                    </td>
                    <td className="px-4 py-3 text-sm font-semibold whitespace-nowrap">
                      {row.estimated_remaining_profit == null ? '—' : money(row.estimated_remaining_profit)}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {row.needs_purchase_cost ? (
                        <button type="button" onClick={() => openCostForm(row)} className="text-sm text-primary-600">
                          Record cost
                        </button>
                      ) : null}
                    </td>
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
            <h2 className="font-semibold text-gray-900">Expenses by Product</h2>
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

      {costForm && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
          <form onSubmit={saveProductCost} className="bg-white rounded-xl w-full max-w-md">
            <div className="p-5 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Record purchase cost</h2>
              <button type="button" onClick={() => setCostForm(null)} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-gray-500">
                Value existing stock and sold units for <span className="font-medium text-gray-800">{costForm.product_name}</span> without changing quantities. Later restocks are recorded as purchase receipts.
              </p>
              <Field label="Unit cost">
                <input
                  type="number"
                  required
                  min="0.01"
                  step="0.01"
                  className="input"
                  value={costForm.unit_cost}
                  onChange={(event) => setCostForm({ ...costForm, unit_cost: event.target.value })}
                  autoFocus
                />
              </Field>
            </div>
            <div className="p-5 border-t flex justify-end gap-2">
              <button type="button" onClick={() => setCostForm(null)} className="btn btn-secondary">Cancel</button>
              <button type="submit" disabled={recordingCost} className="btn btn-primary">
                {recordingCost ? 'Saving…' : 'Save cost'}
              </button>
            </div>
          </form>
        </div>
      )}

      {incomeFormOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
          <form onSubmit={saveIncome} className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-5 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">{editingIncome ? 'Edit share amount' : 'New share amount'}</h2>
              <button type="button" onClick={() => setIncomeFormOpen(false)} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <Field label="Date">
                <input
                  type="date"
                  required
                  className="input"
                  value={incomeForm.income_date}
                  onChange={(event) => setIncomeForm({ ...incomeForm, income_date: event.target.value })}
                />
              </Field>
              <Field label="Shareholder">
                <select
                  className="input"
                  required
                  value={incomeForm.share_partner}
                  onChange={(event) => setIncomeForm({ ...incomeForm, share_partner: event.target.value })}
                >
                  {SHARE_PARTNERS.map((partner) => (
                    <option key={partner.value} value={partner.value}>{partner.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Description">
                <textarea
                  rows={2}
                  className="input"
                  value={incomeForm.description}
                  onChange={(event) => setIncomeForm({ ...incomeForm, description: event.target.value })}
                  placeholder="Optional note about this contribution"
                />
              </Field>
              <Field label="Amount">
                <input
                  type="number"
                  required
                  min="0.01"
                  step="0.01"
                  className="input"
                  value={incomeForm.amount}
                  onChange={(event) => setIncomeForm({ ...incomeForm, amount: event.target.value })}
                />
              </Field>
              <Field label="Additional comments (optional)">
                <textarea
                  rows={2}
                  className="input"
                  value={incomeForm.comments}
                  onChange={(event) => setIncomeForm({ ...incomeForm, comments: event.target.value })}
                />
              </Field>
              <Field label="Payment proof (optional)">
                <PaymentProofInput
                  file={incomeProofFile}
                  existingUrl={incomeProofUrl}
                  cleared={clearIncomeProof}
                  onFileChange={(file) => {
                    setIncomeProofFile(file);
                    setClearIncomeProof(false);
                  }}
                  onClear={() => {
                    setIncomeProofFile(null);
                    setClearIncomeProof(Boolean(incomeProofUrl));
                  }}
                  onRestore={() => {
                    setIncomeProofFile(null);
                    setClearIncomeProof(false);
                  }}
                />
              </Field>
            </div>
            <div className="p-5 border-t flex justify-end gap-2">
              <button type="button" onClick={() => setIncomeFormOpen(false)} className="btn btn-secondary">Cancel</button>
              <button type="submit" disabled={savingIncome} className="btn btn-primary">
                {savingIncome ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </div>
      )}

      {expenseFormOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
          <form
            onSubmit={saveExpense}
            className={`bg-white rounded-xl w-full max-h-[90vh] overflow-y-auto shadow-xl ${receiptEditable ? 'max-w-5xl' : 'max-w-lg'}`}
          >
            <div className="p-5 border-b flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {editingExpense ? 'Edit Expense' : 'New Expense'}
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  {purchaseLocked
                    ? 'This voucher is tied to a stock purchase. Amount, category, product, and quantity stay tied to that stock movement.'
                    : receiptEditable
                      ? 'Record product purchase and update stock automatically.'
                      : 'Record Packaging, Transportation, or Other business costs.'}
                </p>
              </div>
              <button type="button" onClick={() => setExpenseFormOpen(false)} className="p-2 hover:bg-gray-100 rounded-lg" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-5">
              {receiptEditable ? (
                <>
                  <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-4 items-start">
                    <Field label={<>Expense Category<RequiredMark /></>}>
                      <select
                        className="input"
                        value={expenseForm.category}
                        disabled={Boolean(editingReceipt)}
                        onChange={(event) => {
                          const category = event.target.value;
                          setExpenseForm({
                            ...expenseForm,
                            category,
                            lines: category === 'product_buying' && !expenseForm.lines?.length
                              ? [emptyPurchaseLine()]
                              : expenseForm.lines,
                          });
                        }}
                      >
                        {categoryOptions.map((category) => (
                          <option key={category.value} value={category.value}>{category.label}</option>
                        ))}
                      </select>
                    </Field>
                    {isProductBuying ? (
                      <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 lg:mt-7">
                        Product Buying will create a purchase record, add the total amount as an expense,
                        and automatically update warehouse or dealer stock.
                      </div>
                    ) : null}
                  </div>

                  <section className="rounded-xl border border-gray-200 p-4 space-y-4">
                    <h3 className="text-sm font-semibold text-gray-900">Purchase Information</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <Field label={<>Purchase Date<RequiredMark /></>}>
                        <input
                          type="date"
                          required
                          className="input"
                          value={expenseForm.expense_date}
                          onChange={(event) => setExpenseForm({ ...expenseForm, expense_date: event.target.value })}
                        />
                      </Field>
                      <Field label={<>Dealer / Seller Name<RequiredMark /></>}>
                        <input
                          className="input"
                          required
                          value={expenseForm.payee}
                          onChange={(event) => setExpenseForm({ ...expenseForm, payee: event.target.value })}
                          placeholder="e.g. ABC Electronics"
                        />
                      </Field>
                      <Field label="Invoice / Receipt No.">
                        <input
                          className="input"
                          value={expenseForm.invoice_number}
                          onChange={(event) => setExpenseForm({ ...expenseForm, invoice_number: event.target.value })}
                          placeholder="# INV-00000"
                        />
                      </Field>
                      <Field label="Payment Method">
                        <select
                          className="input"
                          value={expenseForm.payment_method}
                          onChange={(event) => setExpenseForm({ ...expenseForm, payment_method: event.target.value })}
                        >
                          {METHODS.map((method) => (
                            <option key={method.value || 'none'} value={method.value}>{method.label}</option>
                          ))}
                        </select>
                      </Field>
                      <div className="sm:col-span-2">
                        <Field label="Notes (Optional)">
                          <textarea
                            rows={2}
                            className="input"
                            value={expenseForm.comments}
                            onChange={(event) => setExpenseForm({ ...expenseForm, comments: event.target.value })}
                            placeholder="Additional comments about this purchase"
                          />
                        </Field>
                      </div>
                      <div className="sm:col-span-2">
                        <Field label="Payment proof (optional)">
                          <PaymentProofInput
                            file={expenseProofFile}
                            existingUrl={expenseProofUrl}
                            cleared={clearExpenseProof}
                            onFileChange={(file) => {
                              setExpenseProofFile(file);
                              setClearExpenseProof(false);
                            }}
                            onClear={() => {
                              setExpenseProofFile(null);
                              setClearExpenseProof(Boolean(expenseProofUrl));
                            }}
                            onRestore={() => {
                              setExpenseProofFile(null);
                              setClearExpenseProof(false);
                            }}
                          />
                        </Field>
                      </div>
                    </div>
                  </section>

                  <section className="rounded-xl border border-gray-200 overflow-hidden">
                    <div className="px-4 py-3 border-b bg-white flex items-center justify-between gap-3">
                      <h3 className="text-sm font-semibold text-gray-900">Purchase Items</h3>
                      <button
                        type="button"
                        onClick={addPurchaseLine}
                        className="inline-flex items-center rounded-lg bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-700"
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        Add Product
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[760px]">
                        <thead className="bg-gray-50 border-b">
                          <tr className="text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                            <th className="px-3 py-3 w-12">#</th>
                            <th className="px-3 py-3">Product</th>
                            <th className="px-3 py-3 w-36">Qty</th>
                            <th className="px-3 py-3 w-40">Unit Price</th>
                            <th className="px-3 py-3 w-48">Discount</th>
                            <th className="px-3 py-3 w-32">Subtotal</th>
                            <th className="px-3 py-3 w-12" />
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {expenseForm.lines.map((line, index) => {
                            const product = products.find((item) => item.id === line.product);
                            const amounts = lineAmounts(line);
                            const qty = Math.max(1, parseInt(line.quantity, 10) || 1);
                            const productOptions = products.map((item) => ({
                              value: item.id,
                              label: item.name,
                              keywords: `${item.sku || ''} ${item.barcode || ''}`,
                            }));
                            const variantOptions = (product?.variants || []).map((variant) => ({
                              value: variant.id,
                              label: [variant.size, variant.color].filter(Boolean).join(' / ') || variant.sku || 'Variant',
                              keywords: `${variant.sku || ''} ${variant.barcode || ''}`,
                            }));
                            return (
                              <tr key={line.key} className="align-top">
                                <td className="px-3 py-3 text-sm text-gray-500 pt-5">{index + 1}</td>
                                <td className="px-3 py-3 space-y-2">
                                  <SearchableSelect
                                    required
                                    value={line.product}
                                    options={productOptions}
                                    placeholder="Select product"
                                    searchPlaceholder="Search product or SKU…"
                                    emptyLabel="No products match"
                                    onChange={(next) => updatePurchaseLine(line.key, {
                                      product: next,
                                      variant: '',
                                    })}
                                  />
                                  {product?.has_variants ? (
                                    <SearchableSelect
                                      required
                                      value={line.variant}
                                      options={variantOptions}
                                      placeholder="Select variant"
                                      searchPlaceholder="Search variant…"
                                      emptyLabel="No variants match"
                                      onChange={(next) => updatePurchaseLine(line.key, { variant: next })}
                                    />
                                  ) : null}
                                </td>
                                <td className="px-3 py-3">
                                  <div className="inline-flex items-center rounded-lg border border-gray-200 overflow-hidden">
                                    <button
                                      type="button"
                                      className="px-2 py-2 text-gray-600 hover:bg-gray-50"
                                      onClick={() => updatePurchaseLine(line.key, { quantity: String(Math.max(1, qty - 1)) })}
                                      aria-label="Decrease quantity"
                                    >
                                      <Minus className="w-4 h-4" />
                                    </button>
                                    <input
                                      type="number"
                                      required
                                      min="1"
                                      step="1"
                                      className="w-14 border-0 text-center text-sm py-2 focus:ring-0"
                                      value={line.quantity}
                                      onChange={(event) => updatePurchaseLine(line.key, { quantity: event.target.value })}
                                    />
                                    <button
                                      type="button"
                                      className="px-2 py-2 text-gray-600 hover:bg-gray-50"
                                      onClick={() => updatePurchaseLine(line.key, { quantity: String(qty + 1) })}
                                      aria-label="Increase quantity"
                                    >
                                      <Plus className="w-4 h-4" />
                                    </button>
                                  </div>
                                </td>
                                <td className="px-3 py-3">
                                  <div className="relative">
                                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">৳</span>
                                    <input
                                      type="number"
                                      required
                                      min="0.01"
                                      step="0.01"
                                      className="input pl-7"
                                      value={line.unit_cost}
                                      onChange={(event) => updatePurchaseLine(line.key, { unit_cost: event.target.value })}
                                    />
                                  </div>
                                </td>
                                <td className="px-3 py-3">
                                  <div className="flex items-center gap-2">
                                    <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs font-medium">
                                      <button
                                        type="button"
                                        className={`px-2.5 py-2 ${line.discount_type === 'percent' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                                        onClick={() => updatePurchaseLine(line.key, { discount_type: 'percent' })}
                                      >
                                        %
                                      </button>
                                      <button
                                        type="button"
                                        className={`px-2.5 py-2 ${line.discount_type === 'fixed' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                                        onClick={() => updatePurchaseLine(line.key, { discount_type: 'fixed' })}
                                      >
                                        ৳
                                      </button>
                                    </div>
                                    <input
                                      type="number"
                                      min="0"
                                      step="0.01"
                                      className="input w-24"
                                      value={line.discount_value}
                                      onChange={(event) => updatePurchaseLine(line.key, { discount_value: event.target.value })}
                                      placeholder="0"
                                    />
                                  </div>
                                </td>
                                <td className="px-3 py-3 pt-5 text-sm font-semibold text-gray-900 whitespace-nowrap">
                                  {money(amounts.total)}
                                </td>
                                <td className="px-3 py-3 pt-4">
                                  <button
                                    type="button"
                                    onClick={() => removePurchaseLine(line.key)}
                                    disabled={expenseForm.lines.length <= 1}
                                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg disabled:opacity-30 disabled:hover:bg-transparent"
                                    aria-label="Remove product line"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </section>

                  <div className="flex justify-end">
                    <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-3">
                      <h3 className="text-sm font-semibold text-gray-900">Purchase Summary</h3>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">Total Items</span>
                        <span className="font-medium text-gray-900">{expenseForm.lines.length}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">Total Quantity</span>
                        <span className="font-medium text-gray-900">{purchaseSummary.totalQuantity}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">Subtotal</span>
                        <span className="font-medium text-gray-900">{money(purchaseSummary.subtotal)}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">Line Discount</span>
                        <span className="font-medium text-gray-900">
                          {purchaseSummary.totalDiscount > 0 ? `− ${money(purchaseSummary.totalDiscount)}` : money(0)}
                        </span>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-gray-500">Additional Discount</span>
                          <span className="font-medium text-gray-900">
                            {purchaseSummary.additionalDiscount > 0
                              ? `− ${money(purchaseSummary.additionalDiscount)}`
                              : money(0)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs font-medium">
                            <button
                              type="button"
                              className={`px-2.5 py-2 ${expenseForm.additional_discount_type === 'percent' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                              onClick={() => setExpenseForm({
                                ...expenseForm,
                                additional_discount_type: 'percent',
                              })}
                            >
                              %
                            </button>
                            <button
                              type="button"
                              className={`px-2.5 py-2 ${expenseForm.additional_discount_type === 'fixed' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                              onClick={() => setExpenseForm({
                                ...expenseForm,
                                additional_discount_type: 'fixed',
                              })}
                            >
                              ৳
                            </button>
                          </div>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            className="input flex-1"
                            value={expenseForm.additional_discount_value}
                            onChange={(event) => setExpenseForm({
                              ...expenseForm,
                              additional_discount_value: event.target.value,
                            })}
                            placeholder="0"
                          />
                        </div>
                      </div>
                      <div className="border-t pt-3 flex items-center justify-between gap-3">
                        <span className="text-sm font-semibold text-gray-900">Grand Total (Expense Amount)</span>
                        <span className="text-xl font-bold text-primary-600">{money(purchaseSummary.grandTotal)}</span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <Field label="Expense category">
                    <select
                      className="input"
                      value={expenseForm.category}
                      disabled={purchaseLocked}
                      onChange={(event) => {
                        const category = event.target.value;
                        setExpenseForm({
                          ...expenseForm,
                          category,
                          lines: category === 'product_buying' && !expenseForm.lines?.length
                            ? [emptyPurchaseLine()]
                            : expenseForm.lines,
                        });
                      }}
                    >
                      {categoryOptions.map((category) => (
                        <option key={category.value} value={category.value}>{category.label}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Date">
                    <input type="date" required className="input" value={expenseForm.expense_date} onChange={(event) => setExpenseForm({ ...expenseForm, expense_date: event.target.value })} />
                  </Field>
                  <Field label="Details / description">
                    <textarea required rows={3} className="input" value={expenseForm.description} onChange={(event) => setExpenseForm({ ...expenseForm, description: event.target.value })} />
                  </Field>
                  <Field label="Amount">
                    <input type="number" required min="0.01" step="0.01" className="input" value={expenseForm.amount} disabled={purchaseLocked} onChange={(event) => setExpenseForm({ ...expenseForm, amount: event.target.value })} />
                  </Field>
                  {purchaseLocked && (
                    <div className="grid grid-cols-2 gap-4">
                      <Field label="Quantity">
                        <input className="input bg-gray-50" value={editingExpense.quantity ?? '—'} readOnly />
                      </Field>
                      <Field label="Unit cost">
                        <input className="input bg-gray-50" value={editingExpense.unit_cost ?? '—'} readOnly />
                      </Field>
                    </div>
                  )}
                  <Field label="Dealer / seller name (optional)">
                    <input
                      className="input"
                      value={expenseForm.payee}
                      onChange={(event) => setExpenseForm({ ...expenseForm, payee: event.target.value })}
                    />
                  </Field>
                  <Field label="Product (optional)">
                    <select className="input" value={expenseForm.product} disabled={purchaseLocked} onChange={(event) => setExpenseForm({ ...expenseForm, product: event.target.value })}>
                      <option value="">Unassigned</option>
                      {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                    </select>
                  </Field>
                  <Field label="Payment method">
                    <select className="input" value={expenseForm.payment_method} onChange={(event) => setExpenseForm({ ...expenseForm, payment_method: event.target.value })}>
                      {METHODS.map((method) => <option key={method.value || 'none'} value={method.value}>{method.label}</option>)}
                    </select>
                  </Field>
                  <Field label="Additional comments (optional)">
                    <textarea rows={2} className="input" value={expenseForm.comments} onChange={(event) => setExpenseForm({ ...expenseForm, comments: event.target.value })} />
                  </Field>
                  <Field label="Payment proof (optional)">
                    <PaymentProofInput
                      file={expenseProofFile}
                      existingUrl={expenseProofUrl}
                      cleared={clearExpenseProof}
                      onFileChange={(file) => {
                        setExpenseProofFile(file);
                        setClearExpenseProof(false);
                      }}
                      onClear={() => {
                        setExpenseProofFile(null);
                        setClearExpenseProof(Boolean(expenseProofUrl));
                      }}
                      onRestore={() => {
                        setExpenseProofFile(null);
                        setClearExpenseProof(false);
                      }}
                    />
                  </Field>
                </>
              )}
            </div>

            <div className="p-5 border-t flex justify-end gap-2">
              <button type="button" onClick={() => setExpenseFormOpen(false)} className="btn btn-secondary">Cancel</button>
              <button type="submit" disabled={savingExpense} className="btn btn-primary">
                {savingExpense ? 'Saving…' : (receiptEditable ? 'Save Purchase' : 'Save')}
              </button>
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
              <Detail label="Dealer / seller" value={selected.payee || '—'} />
              <Detail label="Product" value={selected.product_name || '—'} />
              {selected.purchase_receipt ? (
                <>
                  <Detail label="Receipt" value={selected.purchase_receipt.receipt_number} />
                  <Detail label="Invoice #" value={selected.purchase_receipt.invoice_number || '—'} />
                  <Detail label="Line discount" value={money(selected.purchase_receipt.total_discount)} />
                  <Detail
                    label="Additional discount"
                    value={money(selected.purchase_receipt.additional_discount || 0)}
                  />
                </>
              ) : null}
              <Detail label="Recorded by" value={selected.created_by_name || '—'} />
              <Detail
                label="Payment proof"
                value={selected.payment_proof || selected.purchase_receipt?.payment_proof ? (
                  <a
                    href={getMediaUrl(selected.payment_proof || selected.purchase_receipt?.payment_proof)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary-600"
                  >
                    View proof
                  </a>
                ) : '—'}
              />
              <div className="sm:col-span-2">
                <dt className="text-gray-500">Description</dt>
                <dd className="mt-1 text-gray-900">{selected.description}</dd>
              </div>
              {selected.comments ? (
                <div className="sm:col-span-2">
                  <dt className="text-gray-500">Comments</dt>
                  <dd className="mt-1 text-gray-900">{selected.comments}</dd>
                </div>
              ) : null}
              {selected.purchase_receipt?.lines?.length ? (
                <div className="sm:col-span-2">
                  <dt className="text-gray-500 mb-2">Purchase lines</dt>
                  <dd className="overflow-x-auto border rounded-lg">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          {['Product', 'Qty', 'Unit', 'Discount', 'Total'].map((heading) => (
                            <th key={heading} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{heading}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {selected.purchase_receipt.lines.map((line) => (
                          <tr key={line.id}>
                            <td className="px-3 py-2">
                              {line.product_name}
                              {line.variant_label ? ` (${line.variant_label})` : ''}
                            </td>
                            <td className="px-3 py-2">{line.quantity}</td>
                            <td className="px-3 py-2">{money(line.unit_cost)}</td>
                            <td className="px-3 py-2">{money(line.discount_amount)}</td>
                            <td className="px-3 py-2 font-medium">{money(line.line_total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </dd>
                </div>
              ) : null}
            </dl>
            <div className="p-5 border-t flex justify-end gap-2">
              {(!selected.is_purchase_voucher || selected.purchase_receipt_id || selected.purchase_receipt) && (
                <button type="button" onClick={() => removeExpense(selected)} className="btn btn-secondary text-red-600">
                  <Trash2 className="w-4 h-4 mr-1" />
                  {selected.purchase_receipt_id || selected.purchase_receipt ? 'Cancel purchase' : 'Delete'}
                </button>
              )}
              <button type="button" onClick={() => printExpenseVoucher(selected)} className="btn btn-primary">
                <Printer className="w-4 h-4 mr-1" />
                Print voucher
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="hidden">
        <VoucherPrintBatch ref={printRef} items={printItems} settings={settings} />
      </div>
    </AdminLayout>
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

function PaymentProofInput({
  file,
  existingUrl,
  cleared,
  onFileChange,
  onClear,
  onRestore,
}) {
  const previewName = file?.name || (existingUrl && !cleared ? existingUrl.split('/').pop() : '');
  const link = existingUrl && !cleared ? getMediaUrl(existingUrl) : null;

  return (
    <div className="space-y-2">
      <label className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-lg border border-dashed border-gray-300 px-4 py-3 hover:border-primary-400 cursor-pointer">
        <span className="inline-flex items-center justify-center rounded-lg bg-primary-50 text-primary-700 p-2">
          <Upload className="w-4 h-4" />
        </span>
        <span className="flex-1 text-sm text-gray-600">
          {previewName
            ? `Selected: ${previewName}`
            : 'Upload payment proof (JPEG, PNG, WebP, or PDF, max 5 MB)'}
        </span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf"
          className="sr-only"
          onChange={(event) => {
            const next = event.target.files?.[0] || null;
            onFileChange(next);
          }}
        />
      </label>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {link ? (
          <a href={link} target="_blank" rel="noreferrer" className="text-primary-600 font-medium">
            View current proof
          </a>
        ) : null}
        {(file || (existingUrl && !cleared)) ? (
          <button type="button" onClick={onClear} className="text-red-600">
            Remove proof
          </button>
        ) : null}
        {cleared && existingUrl ? (
          <button type="button" onClick={onRestore} className="text-gray-600">
            Keep existing proof
          </button>
        ) : null}
      </div>
    </div>
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

const VoucherPrintBatch = forwardRef(function VoucherPrintBatch({ items, settings }, ref) {
  return (
    <div ref={ref}>
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
        .voucher-page-break { page-break-after: always; break-after: page; }
        .voucher-page-break:last-child { page-break-after: auto; break-after: auto; }
      `}</style>
      {(items || []).map((item) => (
        <div key={`${item.kind}-${item.id}`} className="voucher-sheet voucher-page-break">
          <h1>PickOrbeet</h1>
          <p className="muted">
            {settings?.contact_address}<br />
            {[settings?.contact_phone_1, settings?.contact_email_1].filter(Boolean).join(' · ')}
          </p>
          <div className="rule" />
          <p style={{ fontWeight: 700, letterSpacing: '0.08em' }}>
            {item.kind === 'income' ? 'INCOME VOUCHER' : 'EXPENSE VOUCHER'}
          </p>
          <table>
            <tbody>
              <tr><th>Voucher number</th><td>{item.voucher_number}</td></tr>
              <tr><th>Date</th><td>{item.date}</td></tr>
              <tr><th>Category</th><td>{item.category_label || '—'}</td></tr>
              {item.kind === 'income' ? (
                <tr><th>Shareholder</th><td>{item.share_partner_label || '—'}</td></tr>
              ) : (
                <tr><th>Product</th><td>{item.product_name || '—'}</td></tr>
              )}
              <tr><th>Description</th><td>{item.description || '—'}</td></tr>
              {item.comments ? <tr><th>Comments</th><td>{item.comments}</td></tr> : null}
              {item.purchase_receipt?.invoice_number ? (
                <tr><th>Invoice #</th><td>{item.purchase_receipt.invoice_number}</td></tr>
              ) : null}
              {item.quantity != null ? <tr><th>Quantity</th><td>{item.quantity}</td></tr> : null}
              {item.unit_cost != null ? <tr><th>Unit cost</th><td>{money(item.unit_cost)}</td></tr> : null}
              <tr><th>Amount</th><td className="amount">{money(item.amount)}</td></tr>
              {item.kind === 'expense' ? (
                <>
                  <tr><th>Payment method</th><td>{item.payment_method_label || '—'}</td></tr>
                  <tr><th>Dealer / seller</th><td>{item.payee || '—'}</td></tr>
                </>
              ) : (
                <tr><th>Recorded by</th><td>{item.created_by_name || '—'}</td></tr>
              )}
            </tbody>
          </table>
          {item.purchase_receipt?.lines?.length ? (
            <table style={{ marginTop: 24 }}>
              <thead>
                <tr>
                  <th style={{ width: 'auto' }}>Product</th>
                  <th style={{ width: 70 }}>Qty</th>
                  <th style={{ width: 90 }}>Unit</th>
                  <th style={{ width: 90 }}>Discount</th>
                  <th style={{ width: 100 }}>Total</th>
                </tr>
              </thead>
              <tbody>
                {item.purchase_receipt.lines.map((line) => (
                  <tr key={line.id}>
                    <td>
                      {line.product_name}
                      {line.variant_label ? ` (${line.variant_label})` : ''}
                    </td>
                    <td>{line.quantity}</td>
                    <td>{money(line.unit_cost)}</td>
                    <td>{money(line.discount_amount)}</td>
                    <td>{money(line.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <div className="signs">
            <div className="sign">Authorized by</div>
            <div className="sign">Signature</div>
          </div>
        </div>
      ))}
    </div>
  );
});
