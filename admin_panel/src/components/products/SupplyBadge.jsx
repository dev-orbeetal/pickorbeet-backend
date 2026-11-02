export default function SupplyBadge({ type, seller }) {
  if (type === 'seller_provided') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-100 text-indigo-700">
        Seller-Provided{seller ? ` · ${seller}` : ''}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700">
      Available Stock
    </span>
  );
}
