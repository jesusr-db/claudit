import { Text, VStack, Button, Center } from "@chakra-ui/react";
import type { InsightCard } from "@/types/api";
import { InsightCardComponent } from "./InsightCard";

const SEVERITY_ORDER: Record<InsightCard["severity"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

interface InsightCardFeedProps {
  cards: InsightCard[];
  analysisError: string | null;
  onRetry?: () => void;
}

export function InsightCardFeed({
  cards,
  analysisError,
  onRetry,
}: InsightCardFeedProps) {
  // Error state
  if (analysisError) {
    return (
      <Center py={8}>
        <VStack spacing={3}>
          <Text color="orange.600" fontSize="sm" textAlign="center">
            {analysisError}
          </Text>
          {onRetry && (
            <Button
              size="sm"
              variant="outline"
              colorScheme="orange"
              onClick={onRetry}
            >
              Try Again
            </Button>
          )}
        </VStack>
      </Center>
    );
  }

  // Empty state — no patterns found (valid result, not an error)
  if (cards.length === 0) {
    return (
      <Center py={8}>
        <VStack spacing={2}>
          <Text fontSize="lg" color="gray.600">
            No patterns detected
          </Text>
          <Text fontSize="sm" color="gray.500">
            This session looks clean — no recurring failure patterns found.
          </Text>
        </VStack>
      </Center>
    );
  }

  // Sort cards: high -> medium -> low
  const sorted = [...cards].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  );

  return (
    <VStack spacing={4} align="stretch">
      {sorted.map((card, i) => (
        <InsightCardComponent key={`${card.type}-${i}`} card={card} />
      ))}
    </VStack>
  );
}
